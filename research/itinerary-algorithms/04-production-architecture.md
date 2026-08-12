# 04 — Production Architecture & Real Products: What Shipping Itinerary Systems Actually Run (2024–2026)

> Lane 4 of 6. Scope: *engineering*, not features. What teams behind real, deployed travel-planning products publicly revealed about architecture — data layers (POI catalogue, routing, distance matrices), orchestration and streaming, caching, evals, determinism — and what that implies for a single developer running an LLM + heuristic-solver itinerary pipeline on cheap infra (this repo: FastAPI + Next.js, `backend/app/pipeline/planner.py`, Postgres 16 + Redis 7, self-hosted OSRM matrix, SSE already in place).
>
> Method: websearch + targeted fetches favoring first-party engineering sources (Google Research blog, Tripadvisor engineering Medium, MIT News, OSRM docs, FastAPI docs) over press. Every load-bearing claim carries inline citations. Evidence strength is labeled: **primary** = first-party engineering writeup/reproducible doc; **secondary** = independent analysis or 2+ corroborating sources; **weak/marketing** = vendor claim, single founder interview, or press copy (used only to anchor, never as proof).
>
> BLUF: No shipping team of any size runs a pure-LLM itinerary engine in production. The documented 2025–2026 converged pattern is **grounding data + LLM-in-the-middle + deterministic solver/verifier**, orchestrated over a streaming HTTP pipeline, with the LLM doing *translation/recommendation/language* and code doing *feasibility*. A solo developer can reproduce ~80–90% of this architecture with one small server, Postgres, Redis, a self-hosted OSRM, and a deliberately boring FastAPI process — the parts that scale cost/latency work *against* solo teams, not for them.

---

## 1. The converged reference architecture (what "modern" actually is)

Every primary engineering source in this survey converges on the same four-layer shape, differing only in where the LLM sits:

```
user query/NL
   │
   ▼
┌─────────────────────────────┐
│ 1. Grounding / retrieval    │  POI catalogue (curated or licensed), hours,
│    (SPARSE first, semantic  │  live data feeds, candidate POIs, nearby
│    second if at all)        │  substitutes
└──────────────┬──────────────┘
   ▼
┌─────────────────────────────┐
│ 2. LLM-as-translator/ranker │  parse NL goals → structured preferences;
│    (NOT the solver)         │  suggest initial plan/candidates; write copy
└──────────────┬──────────────┘
   ▼
┌─────────────────────────────┐
│ 3. Deterministic core       │  constraint validity + feasibility:
│    (solver / verifier /     │  opening hours, budget, travel time/window,
│    heuristics)              │  day packing / routing
└──────────────┬──────────────┘
   ▼
┌─────────────────────────────┐
│ 4. Streaming orchestration  │  SSE/job with status + partial result events,
│    + persistence            │  deterministic plan stored for replay/regen,
│                             │  caching (matrix/route/LLM calls)
└─────────────────────────────┘
```

**Strongest primary evidence — Google's "AI trip ideas in Search"** (June 2025, Research blog): an LLM (Gemini) generates an initial plan; then a **two-stage deterministic optimizer** (per-day dynamic-programming scheduling subject to opening hours and travel time, then a day-level set-packing local search that exchanges activities between days) repairs feasibility, with **search retriever supplying substitute activities** when the LLM's plan can't be made feasible. The blog explicitly names the problem being solved: "LLM-generated plans can at times include impractical elements, such as visiting a museum that would be closed by the time you can travel there." [primary source: https://research.google/blog/optimizing-llm-based-trip-planning/]

**Tripadvisor AI Trip Builder** is the second cleanest public case, and the one that best documents *iteration* on this shape. V1 (July 2023, ChatGPT/OpenAI partnership) used the LLM to suggest recommendations and ranked them by traveler ratings — "we did not use these [reviews] in the formation of our recommendations." A year later they found it wasn't solving traveler problems: "recommendations lacked relevancy." V2 (Aug 2024) inverted the data flow — the **reviews/attraction graph becomes the retrieval/ranking substrate, the LLM wraps it** — and that change *doubled the at-save rate* and improved CSAT by 10%. [primary source: https://medium.com/tripadvisor/cracking-the-code-to-the-ai-travel-planner-27d8d0f222c8; corroborating: https://www.hoteldive.com/news/tripadvisor-openai-ai-travel-trip-itinerary/688500/] Tripadvisor's VP of Data & AI explicitly calls the production lessons: first-party data quality ("you need your data in one place, with high accuracy, taxonomy, and metadata"), input+output QC, and cross-functional measurement. [primary source: https://domino.ai/blog/tripadvisor-ai-trip-builder]

**MIT-IBM Watson AI Lab (2025)** shipped the academic extreme of the same shape: LLM as **translator to a Z3/SMT solver**, not planner. The LLM parses the user's trip prompt into executable Python + constraint annotations; the solver finds a sound, complete solution or returns *which constraints conflict* for the LLM to renegotiate with the user. On TravelPlanner they measured **>90% pass rate vs ≤10% for LLM-only baselines** (GPT-4, o1-preview, GPT-4+tools). [primary source: https://news.mit.edu/2025/inroads-personalized-ai-trip-planning-0610; paper: https://aclanthology.org/2025.naacl-long.176.pdf]. The same translation-to-formal-solver pattern is independently reproduced in the PTS/SCIP system [secondary: https://aclanthology.org/2025.acl-long.1339.pdf] and To the Globe's MILP backtranslation (~91% NL→symbolic exact match, 0.979 cost-ratio to optimum) [secondary: https://aclanthology.org/2024.emnlp-demo.25/].

**GetYourGuide** documents the third face of production: not a solver, but a strict **eval-and-monitoring** discipline around LLM features — LLM-as-judge agreeing with humans >80%, Arize Phoenix tracing, batch eval jobs, "human in the loop cannot completely be automated." [primary-ish presentation, weak on specifics: https://www.slideshare.net/slideshow/the-journey-of-large-language-models-at-getyourguide/271735335]

### 1.1 Proven vs claimed, by product

| Product | Verified engineering (primary) | Claimed (marketing/press) |
|---|---|---|
| Google Search AI itineraries | Hybrid LLM+optimizer, Search-retrieved grounding, per-day DP + day-level set packing [primary: research.google/blog/optimizing-llm-based-trip-planning/] | — |
| Tripadvisor Trips AI | V1 LLM-rank-by-rating; V2 first-party-review-grounded, doubled save rate, +10% CSAT [primary: Tripadvisor Medium] | "2.9M itineraries generated" [weak/marketing: MarCom entry] |
| GetYourGuide | LLM-as-judge ~>80% human agreement; Phoenix tracing [primary-ish slides] | AI review summaries, itinerary builder features [weak/marketing] |
| Mindtrip | Team structure: "psychotherapist to the LLM," AI streaming + trip-planning engineers; "proprietary travel knowledge base," ~6.5M POIs [secondary: devwork.be, eightception] | "personalized," "start anywhere" [marketing] |
| Expedia Romie / Layla | Group-chat planning, LLM assistant over Expedia supply; later acquired Layla [secondary: travelpress/PhocusWire] | "agentic," "end-to-end booking" |
| Wanderlog | Collaborative CRUD itinerary + Google Maps route visualization; gmail import; AI assistant, per YC listing [weak: YC / businessmodelcanvastemplate] | "10M itineraries," "98% email parse" [marketing-grade, single vendor] |

**Takeaway for confidence:** the only *architectural* claims you should treat as load-bearing are Google's, Tripadvisor's, and the academic-installed systems. Everything else describes UX, not stack. No product has publicly revealed an equivalent of `planner.py` — its adoption of a deterministic scheduler with an LLM for copywriting is *consistent with* the documented shipping pattern, not exotic.

---

## 2. Data foundation: the catalogue is the product; OSM is the trap

### 2.1 Who owns the POI catalogue

- **Tripadvisor**: its own UGC corpus (1B+ reviews) *is* the catalogue; data quality pipeline is the moat [primary: domino.ai, medium.com both above].
- **Mindtrip**: proprietary ~6.5M POI knowledge base, "constantly updated" [secondary: https://eightception.com/mindtrip-ai-travel-startup/ — founder-adjacent, treat counts as claimed].
- **Google**: owns Places data; no plumbing released.
- **Independents**: Google Places API (licensed), Foursquare OS Places, Overture Maps, or self-curated OSM extracts.

### 2.2 POI data quality — the evidence that it's the #1 bottleneck

The failure mode named by every shipping team is *stale/wrong POI attributes*, not the solver:

- "It'll recommend a restaurant that shut down two years ago… users notice on day one, standing in front of a locked door." [agency account of a real build: secondary/weak https://www.teacode.io/blog/how-to-build-ai-trip-planner-app]
- Google's whole optimizer stage exists because the LLM cannot know "establishment that has recently closed" — *grounding data* must come from a maintained catalogue [primary: research.google blog].
- Tripadvisor restructured around first-party reviews after discovering the LLM's suggestion space was worse than their own data [primary: Tripadvisor Medium].

Peer-reviewed OSM POI quality work quantifies the problem for open data: **completeness of OSM POIs is category- and place-dependent**, missing-POI counts rise with real-world density, and private-business/service categories are systematically under-mapped [primary-ish: https://journals.sagepub.com/doi/full/10.1177/03611981231169280]. A 2026 benchmark against a chain's 19 verified stores found OSM covered 5 of them (26%) while a paid dataset at 95.6% attribute fill [secondary, vendor-published but methodical: https://www.safegraph.com/blog/comparing-safegraph-and-openstreetmap]. The OSM community itself documents why *opening hours* specifically are the hardest attribute: providers can't bulk-import reliably (import permission/rework iterations, format mismatches, no stable company pipeline) — "OSM doesn't have [hours] and Google does… not because Google crowdsources it but because Google is easy and OSM is bureaucratic" [primary-ish forum threads: https://community.openstreetmap.org/t/how-can-openstreetmap-better-collaborate-with-businesses-seeking-to-provide-information-such-as-opening-hours/119791].

**Decision implication for this repo** (3,508 curated OSM places, `KNOWN_HOURS_BY_NAME` overrides, `visit_guidance`): the curated-layer-on-top-of-OSM design is already the *industry-consistent* answer at solo scale. What real teams add that this repo should mirror:
1. A **single source-of-truth schema** with explicit quality metadata (source, verified flag, next-check date) — Tripadvisor's "high accuracy, taxonomy, and metadata" point [primary: domino.ai].
2. A **tiny refresh pipeline** (weekly or monthly) rather than an import-once dataset; see §7.2.
3. **Deliberate degradation UX** for unknown hours (the repo's "Kiểm tra giờ mở cửa trước khi đi." note is exactly the pattern shipping products keep).

### 2.3 Distance matrices: OSRM self-hosted is the documented cheap path

A distance/time matrix is the most expensive ingest in any itinerary system. The 2026 consensus among production guides is unambiguous:

- **OSRM `/table` API**: self-hosted, no per-element fee, unbounded rate, "100×100 matrix (10,000 elements) in a few dozen ms," 5,000–10,000 QPS on an 8-core box, matrix-appropriate CH preprocessing (official Docker image recommends CH for very large matrices) [secondary guides: https://dev.to/vesviet/system-design-graphhopper-distance-matrix-self-host-osrm-vs-haversine-for-route-optimization-2cpg; https://tanhdev.com/series/ecommerce-order-allocation/part-7-distance-matrix-routing; https://github.com/Qalfredo/osrm-production-deploy-and-math; https://hub.docker.com/r/osrm/osrm-backend/].
- Cost contrast used by the same guides: Google Maps Distance Matrix ~$5/1k elements ($510/day for 10,201 pairs) vs ~$0.03 infra-only self-hosted [secondary: osrm-production-deploy-and-math; dev.to above]. Google's own 2025 pricing restructure removed the flat $200 credit and split free tiers per-SKU (10k/mo Essentials, 5k/mo Pro Places SKUs) — any substantial matrix workload on Google is now clearly billable [secondary: https://maps.guru/blog/google-maps-api-pricing-explained-2026; primary pricing: https://developers.google.com/maps/billing-and-pricing/pricing].
- **Memory budget** for self-hosting: MLD country extracts ~3–5 GB (Germany/France), ~1–3 GB for a US state; CH slightly lighter; a 4 GB box runs most single-country cases [secondary: https://sumguy.com/self-hosted-osrm-docker]. Vietnam (~less than Germany-sized extract) fits comfortably on a $6–20/month VPS with headroom. This matters: **solo cost ceiling is set by RAM, not feature cost.**
- **CH vs MLD**: CH for max matrix throughput on a stable profile (this repo's case), MLD when you iterate on speed models. Both are `docker run`-able from the official image [secondary: sumguy.com; hub.docker.com above].

### 2.4 Caching strategies that actually work small-scale

- **H3-hexagon route-cost cache (Uber's pattern, adapted)**: convert endpoints to H3 res-9 cell IDs, cache `route_cost:{h3A}:{h3B}` in Redis with ~30-day TTL, nightly pre-warm for realistic pairs, >95% hit ratio cited; grid-cache avoids recomputing nearby-pair routes thousands of times [secondary: dev.to/vesviet; tanhdev guide above].
- **Hybrid haversine prefilter**: never call the matrix for pairs with straight-line distance above a threshold (or assign ∞); haversine filter reportedly cuts solver prep ~30% [secondary: dev.to/vesviet comment + body].
- **Annotated matrix reuse**: store the *annotations* (duration+distance) with the pair key, not just the geometry, since solvers resample the same pairs across days/plans.
- **What NOT to do at solo scale**: a full N×N matrix for every request. This repo's current approach (precomputed verified matrix for a fixed 3,508-POI catalogue + per-request haversine fallback) is the correct scaling posture; cache-miss-mediated OSRM calls on demand, as above.

---

## 3. Streaming + async orchestration: SSE is the 2026 default, keep it boring

### 3.1 The documented pattern

The FastAPI/SSE stack this repo already uses is the industry-standard 2026 shape: **unidirectional SSE beats WebSockets for LLM token streaming** (plain HTTP, proxy-friendly, browser-native `EventSource`); WebSockets reserved for true bidirectional voice/agent cases [secondary, several: https://www.callmissed.com/blog/tutorial-stream-llm-fastapi; https://fastapi.tiangolo.com/tutorial/server-sent-events/]. Real production gotchas, all documented:

1. **Sync client blocks the event loop.** Wrapping the (sync) OpenAI/Anthropic streaming call in `asyncio.to_thread()` + an `asyncio.Queue` pump is the canonical fix; naive `async def` wrappers add 1–3 s of dead-air before first token [secondary: https://mr.technology/payloads/tutorial-fastapi-llm-streaming-server-sent-events].
2. **Check `request.is_disconnected()` per chunk** — costs real money otherwise ("bill doubled after a frontend bug caused users to navigate away mid-stream") [secondary: mr.technology].
3. **Bump proxy/load-balancer timeouts** (300 s+) and set `X-Accel-Buffering: no`; ALB/Cloud Run/nginx buffering silently kills SSE [secondary: https://johal.in/implementing-llm-streaming-responses-with-server-sent-events-and-fastapi; devopsboys guide].
4. **Async generator + `EventSourceResponse`**, with distinct named events (`event: status`, `event: result`, `event: error`) so clients can render incrementally [primary docs: fastapi.tiangolo.com; this repo already does exactly this in `plans.py:150-164`].

### 3.2 Job queue vs on-the-fly: solo-dev verdict

The current repo generates **on-the-fly inside the SSE handler** (`build_plan` on a thread), which is the right call at this scale: the work is bounded (a few seconds of solver code + optional LLM copy), and streaming hides that latency. Production guides agree the threshold for introducing a job queue (Celery/RQ/Dramatiq) is when requests exceed client tolerance, need durable retry, or outlive the request — not before [secondary: https://python.plainenglish.io/handling-background-tasks-and-long-running-jobs-in-fastapi-the-complete-guide-b197d38145d7]. Celery/RQ adds a worker process + Redis broker + monitoring for a single-user-per-machine workload that *already* has Redis. **Recommendation: stay in-request (threaded) as long as the hot path ≤ ~10–20 s; introduce a queue only when (a) multi-step agentic work or (b) concurrent traffic above roughly one worker's capacity appears.** Evidence from products: Tripadvisor's 10–15 s first-draft latency is treated as a feature boundary, not a job-queue trigger [secondary/weak: https://www.realjourneytravels.com/tripadvisor-ai-trip-planner-review].

### 3.3 Incremental rendering and regen

Shipping products stream *structured status* rather than only tokens: Google's Search itineraries render day-by-day cards; Tripadvisor returns day cards progressively. The repo's status events (`finding_places` → `routing_plan` → `result`) are the right granularity; the one upgrade worth making is **persisting phase output** (candidates found, matrix computed, day skeleton) so a dropped connection can *poll-resume* rather than fail — the nonce/replay path in `plans.py:121-138` already implements the "identical request → replay stored deterministic result" half of this. That is a genuinely production-grade touch most startups lack.

---

## 4. Evaluation infrastructure: the least-mature part everywhere

Trip-specific evaluation is the youngest layer in every team's stack. The documented hierarchy:

1. **Deterministic code guardrails (mature, cheap, non-negotiable).** Constraint checks — budget sum, opening-hour/visit-window feasibility, travel-time sanity, JSON schema validity — are pure functions, run on 100% of outputs, never disagree with themselves [secondary: https://www.langchain.com/resources/how-to-evaluate-llms; this repo's `PoC-1` schema-validation gate in README is exactly this].
2. **LLM-as-judge (standard in travel since 2024, but calibration caveats).** GetYourGuide: judge-human agreement >80% ("same level of agreement between humans") [primary-ish slides above]. Papers quantify the current caveats: even top judge models (Gemini-2.5-Pro, GPT-5) fail to maintain consistent preferences in ~a quarter of hard cases, with position/verbosity biases [secondary: December 2025 study summary in langchain.com/resources/how-to-evaluate-llms; https://arxiv.org/abs/2512.16041]. Applied to travel, LLM-judges are used for preference/personalization ranking (PTS "LLM judge presented with pairs of travel plans alongside user profiles" [secondary: https://aclanthology.org/2025.acl-long.1339.pdf]) and for rationality scoring (TripTailor's "feasibility ≠ rationality" 3–4× route-distance gap [secondary: https://aclanthology.org/2025.findings-acl.503/]).
3. **Benchmarks as regression harnesses (not marketing claims).** TravelPlanner is the standard hard-constraint suite (human-verified; every query solvable) [primary: https://github.com/OSU-NLP-Group/TravelPlanner]. Newer suites add real production queries and stable tool caching: TravelBench caches ~200k real tool responses for reproducible eval and reports LLM-judge sd ≈ 0.01 across runs [secondary: https://aclanthology.org/2026.acl-long.1347.pdf]; TripScore freezes an operator-curated POI snapshot and unifies "multifaceted criteria into a single reward" [secondary: https://arxiv.org/html/2510.09011v3]. None of these substitute your own data.
4. **Product-level human metrics (the ones Tripadvisor actually reports):** itinerary save rate, 7-day return rate, CSAT, revenue multiplier (itinerary-builders → ~3× revenue of average member) [secondary: https://www.travelweekly.com/Travel-News/Travel-Technology/Tripadvisor-sees-dollar-signs-generative-AI]. These are the north-star evals, and they cost nothing but analytics.

**Solo-dev practical build:** (1) a deterministic validator run over slipped test fixtures (the repo's `PoC-1` 20-scenario JSON gate), (2) a small `LLM-as-judge` pair- or rubric-eval over N=30–50 triaged cases with manual spot-checking, (3) one dash of product telemetry (save rate, regen rate, satisfaction). That covers ~90% of what any team above does, at ~zero infra cost.

---

## 5. Serving layer: routing engines and geo indexing

For an offline-capable, cheap Vietnamese product the engine decision is essentially closed:

| Criterion | OSRM | Valhalla | GraphHopper |
|---|---|---|---|
| Matrix speed | Fastest (C++/CH) | Slower | Middle |
| Isochrones | No | Yes | Yes |
| Transit/multi-modal | No | Yes (GTFS) | Yes (GTFS) |
| Profile changes | Lua + recompile | JSON costing at query time | Custom models, no rebuild |
| `trip`/TSP endpoint | `trip` service | Optimized route/TSP | No |
| Full-planet RAM | ~55 GB | tile-based, lower base | ~40–60 GB |
| Docker | Official | Official | Community |

[secondary comparisons: https://www.pistack.xyz/posts/2026-04-25-graphhopper-vs-osrm-vs-valhalla-self-hosted-routing-engines-guide-2026; https://sumguy.com/osrm-vs-valhalla-vs-graphhopper; https://mapsi.dev/developers/routing-engine-comparison]

- **Verdict for this product:** OSRM with **CH** for the fixed driving profile and matrix throughput — it is the only engine whose own maintainers recommend CH "for very large distance matrices" [primary: hub.docker.com/osrm/osrm-backend]. If and when walking/motorbike costing or isochrones matter, Valhalla is the drop-in richer engine (per-request JSON costing, no rebuild), still self-hosted.
- **Geo indexing:** at 3,508 POIs, PostGIS R-tree *and* in-memory dictionaries both work; PostGIS earns its keep only when the catalogue grows to tens of thousands *and* queries become spatial (buffered nearby search, clustering). Do not add a vector DB for POIs: keyword/tag matching (this repo's `INTENT_PROFILES`) outperforms semantic search for well-typed POIs, and pgvector-in-Postgres (for descriptions) is the only justified embedding path [secondary: teacode recommends "PostgreSQL + pgvector; one DB for relational data and embeddings"; https://www.teacode.io/blog/how-to-build-ai-trip-planner-app].
- **Refresh pipeline:** OSM extracts refresh monthly from Geofabrik (roads change slowly; POI edits happen continuously). A monthly `osrm-extract → partition/contract` job + a catalogue sync job is the documented cadence [secondary: sumguy.com osrm article; pistack FAQ "how often should I update OSM data"].

---

## 6. Determinism & reproducibility: the actual mechanisms

Real teams achieve reproducibility the boring way — they *don't* ask the LLM to make decisions where a deterministic component suffices, and they cache/freeze everything else. Documented mechanisms:

1. **Deterministic core for anything a human can check.** Google's optimizer, MIT's SMT solver, Tripadvisor's review-graph ranking, and this repo's hash-seeded scheduler (`_request_seed`, `_place_seed`) all place stable decision-making in code. That is determinism-at-the-source, and it's why the repo can promise "identical request → identical plan."
2. **Seeded stochasticity.** Where randomness or heuristic search is used (two-opt, local search), a request-derived seed makes reruns stable — Google's set-packing local search converges deterministically given the same inputs; MIT's solver is fully deterministic given the same constraints.
3. **Versioned + frozen data.** TravelBench explicitly caches ~200k tool responses "to provide stable and consistent tool outputs during evaluation" [secondary: aclanthology 2026.acl-long.1347]; TripScore "freezes" its POI snapshot [secondary: arXiv 2510.09011v3]. The analogue in a production itinerary service: **immutable catalogue snapshots + OSRM graph version tags**, so plan reproducibility is guaranteed across data refreshes, and only a new snapshot id changes the plan family. This is the single most underrated lever for "deterministic-ish reproducible plans."
4. **LLM+solver determinism trade-off:** the LLM output (preferences, candidates, copy) is nondeterministic and *expensive to freeze*; teams therefore make llm-nondeterminism *cosmetic-adjacent* (preferences → deterministic candidates → solver → llm copywriting) so that *plan identity* is stable even when phrasing drifts. The repo's split (LLM for selection/copywriting on top of a deterministic scheduler) already matches this; the improvement is to make the LLM *selection* stage accept an explicit `seed`/model-version parameter too, and cache per (catalog-version, intent, seed).

---

## 7. What a solo developer should build — and what to skip

### 7.1 Skip list (evidence-grounded)

1. **Multi-agent orchestration frameworks (LangGraph-style).** The only compute-matched comparison found in this whole deep dive measured a planner-executor multi-agent at **177,560 tokens/query vs 89,013 single-agent, for a +5.2pp commonsense gain, no final-pass-rate gain, and 2× cost on 7-day trips** [secondary, thesis-grade rigor: https://essay.utwente.nl/essays/111014]. Anthropic's canonical guidance is the same shape: "use the simplest solution that works," workflows > free-form agents, single agent with a few tools beats agent teams for well-scoped tasks [primary: https://www.anthropic.com/engineering/building-effective-agents]. Your task (one city, one request → one plan) is exactly the "well-scoped task" that a graph buys you latency and tokens for free. There is no production evidence that multi-agent travel planners out-earn their unit economics.
2. **Vector DBs as a primary store.** Your catalogue is 3,508 typed places; tag/keyword retrieval is stronger and Cheaper. Evidence: Tripadvisor *removed* reliance on generalist LLM knowledge in favor of first-class review data; Google grounds in Search for *substitutes* — semantics located in retrieval, not in a vector corpus. (pgvector later, only for free-text description search.)
3. **Caching telemetry + eval dashboarding before the deterministic validator exists.** Every eval framework agrees: deterministic functional checks first, judge calibration second, dashboarding last [secondary: langchain review]. 
4. **Kubernetes / autoscaling.** A single server (or 2 cheap VPS: app+PG/Redis+OSRM) is the documented solo shape; "serverless pays off" only above a certain traffic floor. (Google's production infra is irrelevant — it's a search engine.)

### 7.2 Build list (what real teams would recognize)

1. **Catalogue-with-metadata as the product's spine** (verified flags, source, hours overrides, next-check date) — Tripadvisor's #1 lesson, directly transplantable to the existing `visit_guidance`/`KNOWN_HOURS_BY_NAME` machinery.
2. **Snapshot/versioned data + seed params** (§6.3) so "same input → same plan" is a *guaranteed contract*, not an accident.
3. **On-the-fly SSE with disconnect-detection + replay on nonce** (mostly already implemented; add `is_disconnected` + phase persistence for resume).
4. **OSRM CH matrix server + Redis H3-cached routes**, with haversine prefilter for long pairs (§2.4). ~2 days of work, eliminates the entire matrix cost forever.
5. **Deterministic validator harness** (PoC-1 style, on every push) + N=50 LLM-judge rubric eval with human spot-check + product telemetry (save rate, regen rate). This is the entire eval budget that beats most teams.
6. **A mock/frozen data mode for CI** that exercises the *solver* path deterministically — this repo's `AI_MODE=mock` already does exactly this; keep it forever.

---

## 8. Severity-flagged findings

| # | Finding | Severity |
|---|---|---|
| 1 | LLM-only itinerary engines are not a production reality anywhere; the documented 2025–26 shape is grounding data + LLM-in-the-middle + deterministic solver/verifier. Adopt/advertise that framing, not "AI plans your trip." | High (architectural truth) |
| 2 | POI attribute freshness (hours, closures) — not the algorithm — is the top failure mode of shipping products and the worst-studied weakness of OSM data. Budget curation/refreshes accordingly. | High |
| 3 | Self-hosted OSRM (CH profile) for matrices + H3-cached route costs is the cheap, proven, offline-capable fill-in for the current verified-matrix approach; no paid matrix API needed at this scale. | Medium |
| 4 | SSE on-the-fly generation (current design) is correct; add `is_disconnected()` checks and phase-persistable replay. Do not add Celery/queue until hot-path exceeds ~10–20 s or concurrency demands it. | Medium |
| 5 | Determinism comes from frozen data snapshots + deterministic solver + seed-able LLM selection stage, not from prompting tricks. Implement snapshot version + seed propagation. | Medium |
| 6 | Multi-agent orchestration and vector-DB-first retrieval are net-negative at solo scale; no production evidence of payout (token cost 2×, no accuracy gain). Skip. | Medium |
| 7 | Eval stack should be deterministic validators → calibrated LLM-judge → product telemetry. This, not a dashboard, is the maturity signal. | Low |
| 8 | PostGIS/pgvector only when catalogue grows to tens of thousands and spatial description search appears; today in-memory + Postgres is sufficient and simpler. | Note |
| 9 | Wanderlog/Mindtrip/Layla "architecture" claims are mostly UX marketing; do not mine them for engineering decisions. | Note |

---

## Appendix — Exec summary (≈250 words)

The modern production architecture for an automated itinerary generator is not an LLM solving a problem end-to-end; it is a **hybrid pipeline** that every team that has disclosed engineering (Google Search itineraries, Tripadvisor's AI Trip Builder, MIT-IBM's SMT travel broker) converges on: a grounded, owned POI catalogue with quality metadata; an LLM that translates preferences and drafts language **rather than making feasibility decisions**; a deterministic core (solver or verifier) that enforces opening hours, budget, and travel time; and a streaming orchestration layer (SSE) that renders progress and replays stored results. The hard, repeatedly documented failure point is **data freshness, not math** — "it'll suggest a museum that's closed." For a solo Vietnamese builder, every load-bearing component is already runnable on cheap infra: Postgres 16 + Redis 7 (already in place), a self-hosted OSRM CH server for distance matrices (memory-cheap for Vietnam, ~$10/mo, offline-capable), on-the-fly SSE with disconnect handling and nonce-replay (already in place), and a deterministic, hash-seeded scheduler (already the repo's core). The deltas that would bring this repo to the documented industry shape are: treat the 3,508-POI catalogue as a versioned, quality-tagged asset with a refresh cadence; add H3/Redis caching for route costs; make plan outputs a *contract* via snapshot version + seed propagation; install a three-layer eval stack (deterministic validators → LLM-judge with human spot-check → product telemetry), and deliberately skip multi-agent frameworks and vector databases, for which no production evidence of payoff exists at this scale.

## Top 5 findings

1. **Converged reference architecture** — grounding/retrieval → LLM-translator → deterministic solver/verifier → SSE streaming; confirmed by Google, Tripadvisor, and MIT-IBM primary sources (Google Research, 2025; Tripadvisor Tech, 2024–25; MIT News, 2025).
2. **The catalogue is the product.** POI freshness (hours/closures) is the #1 shipped-product failure mode and OSM's weakest dimension (26% coverage vs a paid dataset in one benchmark; systematic under-mapping of private business categories); curated-overlays + metadata + refresh cadence is the industry answer.
3. **OSRM self-hosted (CH) + H3/Redis route caching** is the documented, near-$0 path for distance matrices (10k-element matrix in tens of ms; ~$0.03/element-equivalent vs Google's $5/1k); fits Vietnam on a tiny VPS and stays offline-capable.
4. **Evaluation is deterministic-validators-first, LLM-as-judge second (calibrated; >80% human agreement documented but judge instability is real), product-metrics third**; nothing substitutes the planner's own constraint-checking harness.
5. **For a solo dev, on-the-fly SSE with disconnect-safe, replayable requests is the right orchestration; job queues and multi-agent/vRAG stacks are deferred until traffic or task complexity genuinely demands them** (multi-agent measured at 2× token cost with no pass-rate gain).

## Confidence & ground-truth tally

**Confidence: 8/10** on the architectural synthesis and the infra recommendations; 7/10 on eval and determinism prescriptions (youngest evidence base, some vendor-adjacent sources); 6/10 on product-specific claims by non-Google/Tripadvisor vendors (mostly marketing).

**Ground-truth tally: 8 of 16 load-bearing conclusions externally verified** via 2+ independent sources or primary engineering documentation:
- Hybrid LLM+solver convergence (Google Research blog + MIT News/NAACL paper + Tripadvisor Tech), ✅
- POI freshness bottleneck (OSM POI quality study + SafeGraph benchmark + Tripadvisor data-Q lessons), ✅
- OSRM matrix cost/latency/memory + CH-for-matrix (OSRM Docker docs + 3 production deploy guides), ✅
- SSE streaming pattern + disconnect gotchas (FastAPI docs + 2 production guides), ✅
- LLM-as-judge adoption + calibration caveats (GetYourGuide slides + arXiv 2512.16041 + langchain synthesis), ✅
- Freeze/caching for reproducibility (TravelBench + TripScore papers), ✅
- Google pricing restructure (Google pricing page + secondary pricing guide), ✅
- Routing engine comparison table (2 independent comparison guides + engine docs), ✅

Model-judgment-only: multi-agent token-cost verdict (single thesis-grade source + Anthropic guidance — treated as directional), H3 cache hit-rate ~95% figure, "queue only past ~10–20 s," pgvector-only-when-scaled guidance, hw sizing for Vietnam extract, Google's 10–15 s UX boundary, Wanderlog/Mindtrip architecture reads.