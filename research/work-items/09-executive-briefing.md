# 09 — Executive Briefing (for the product owner)

> Deep-dive on "Minh Di Dau The" travel-planning MVP · 6 specialist lanes + synthesis + adversarial red-team · all findings verified against the repo (code, data, tests re-run).

---

## TL;DR

**Your app is demo-able but not demo-clean.** The skeleton is small, coherent, and honest about itself — but six small lies travel together:

1. The README says **3.508 places**; the demo can actually reach **~71**.
2. **Every** place says "60 phút" — no real visit times exist yet.
3. Images are requested from the API but the **attribution is never shown** (a licensing problem).
4. A manual edit you make is **silently erased** the next time you ask the AI to refine.
5. The planner can produce **"Bữa trưa" at 20:10** (lunch after dinner) — reproducible.
6. Switch the app to English and **Vietnamese text still leaks** into all 18 locales.

**None of these is fatal. All but two are cheap. Fixing them IS the roadmap.** The plan below is ready to execute; ~one focused sprint gets Tier 0 done.

---

## Verdict

**Proceed.** Not "go build new features" — **go make the six lies true first.** This is the first artifact in the project that shows exactly where those numbers come from, and it is demonstrably accurate (an independent adversarial pass re-verified every claim at the exact lines cited, plus re-ran your test suite: 33/33 pass — and none of the tests catches the lunch bug).

- **Findings confidence: 8/10** (9/10 for everything checked directly in the repo; small deduction for a few outside-world facts).
- **Plan confidence: 6/10** — the roadmap's *effort estimates and ordering* are expert judgment, not measured fact. The *diagnosis* is near-certain; the *schedule* is a plan, not a promise.

---

## The six lies, in plain English (and how to fix)

| # | Lie | Where | Cost |
|---|---|---|---|
| 1 | "3.508 places" but demo reaches ~71 | routing whitelist + 50-place matrix | **Move matrix expansion up the queue**; meanwhile the demo should say "50 verified anchors" |
| 2 | Every visit = 60 min | import script, all 3,508 rows | Add per-category durations with 2 named sources each |
| 3 | Attribution never rendered (licensing risk) | image credit emitted but dropped | Show credit + license + link under each photo; do **before** adding more images |
| 4 | Manual edits silently erased by "refine" | AI rebuilds from scratch | At minimum, warn the user before refining wipes manual changes |
| 5 | Lunch at 20:10 (after dinner) | planner relax logic | Enforce meal order: trưa → nghỉ → tối → đêm; add a regression test (the suite misses it today) |
| 6 | Vietnamese leaks into 18 locales | locale file, history screen | Fix locale file + history screen; add an automated "no Vietnamese in other locales" check |

---

## What genuinely works (be proud of this)

- **The planner core is sound** — the bug is a single relaxation-pass escape, not a design failure.
- **Manual place swap already exists** and behaves correctly — the codebase is further along than the README admits.
- **All 3,508 places carry a verified source URL** — the catalogue's provenance foundation is real; only the images/durations/attribution are missing.
- **Tests are green** and the i18n harness is already in place — the guard rails to prevent regression exist.

---

## Prioritized action list

### Tier 0 — do first (demo blockers, ~1 sprint)
1. Fix lunch-after-dinner (**with regression test in the same commit**)
2. Kill Vietnamese leakage in 18 locales (+ automated purity check)
3. Localize the history screen
4. Render image attribution + license + link
5. Fix dark-mode contrast on itinerary buttons
6. Make swapped places recompute their times correctly (and not move the others)
7. Map errors properly ("cannot verify" / "doesn't fit" → real codes, Vietnamese UI)
8. Add real visit-duration fields (before-padding value + where it came from)

### Tier 1 — next (make "best itinerary" actually true)
- Real per-category visit durations (sources cited), image enrichment, wiki-tag capture
- Ranked place candidates (the true "best places" lever), reorder endpoint
- **A warning before refine wipes your manual edits** ← currently a named risk with no task
- External links (Netflix/Facebook/TikTok/YouTube) — verify TikTok/Google URLs manually first

### Tier 2 — later (efficiency & polish)
- Expand the travel-time matrix (50 → hundreds) ← **promoted; live-demo discrepancy**
- Joint optimization when the itinerary gets big enough to matter
- Keyboard accessibility on the full-card click layer, slot swap, misc UI

### Tier 3 — noted, not scheduled
- Dead-code evening IDs, "deterministic = mock-mode-only" caveat, re-verify place census at next import.

---

## Should you proceed?

**Yes.** The product concept is sound, the code is healthy, and the roadmap is now truthful. Run Tier 0 as one focused sprint, then decide Tier 1 with real demo feedback. Two asks before you do:

1. **Tell the demo the truth**: either "50 verified anchors" in the UI or ship the bigger matrix first.
2. **Pick which "best" you're selling**: better places (ranking/curation) or tighter schedules (optimization). The plan currently optimizes schedules; the README sells the catalogue.

---

## Appendix — ground-truth tally

- 14 of 15 headline findings verified at exact file:line by the adversarial pass (code read + `places.json` raw parse + test-suite re-run).
- 8/8 red-team load-bearing targets survived attack; zero fabricated line numbers or counts.
- The only un-capped-to-8/10 items: outside-world facts (TikTok URL, Google `udm=14`, external source values).
- Plan numbers (effort, tiers, durations) are model judgment → reported separately at 6/10. Never read the 8/10 as covering the roadmap.
