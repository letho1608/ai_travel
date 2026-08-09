# 06 — Synthesis (unified aesthetic audit)

Reads all five specialist lanes plus rendered ground-truth; cross-checks load-bearing claims against the actual code; resolves contradictions.

**Scope:** PURELY VISUAL/AESTHETIC beauty of the "Mình Đi Đâu Thế" frontend (`frontend/app/globals.css` design system). NOT functionality. Ground truth captured via headless Edge 151 CDP + pixel analysis; see `00-ground-truth.md`.

---

## Unified verdict

**Overall beauty score for the CURRENT code state: 4.5/10** (lane spread: components 6.5, color-cohesion 5.5, layout-consistency 5.0, page-level average 4.6 — landing 7.0 → history 2.5, typography the weakest ~3).

Weighting by what users actually see: a coherent, tastefully-tokenized violet design system whose delivery fails on the three things that carry perceived beauty — the fonts never load (all text renders Segoe UI), the default light theme is 95% blank near-white, and the flagship screen has a visible horizontal-overflow defect. Two dark-mode defects (invisible text-selection, broken CTA banner) and two leftover-brand map colors puncture cohesion. The bones are genuinely above the AI-startup median; the render is not.

## What the app does BEAUTIFULLY

1. **Disciplined harmonious palette** — all brand chroma at hue 261–266°, warm paper `#f7f6f3` (H=45), plum-black ink `#2a182e` (H=289), plum-tinted shadows `rgba(42,24,46,…)`. A real point of view (`globals.css:1`).
2. **Plum-tinted shadow scale + lavender ring language** — `sm/xl` at 5–16% alpha; `0 0 0 4px var(--lavender-soft)` focus/slot-selected/assistant-dot halos. Best "shadow language" in the app (`globals.css:1,25`).
3. **The itinerary slot grid** — `28px index / 56px time / flexible title / auto`, description indented via `grid-column:2/-1`, selected-ring affordance (`globals.css:25`; `PlanView.tsx:128`).
4. **Landing hero composition** — 1.05fr/.95fr, 56px gutter, 88px display headline `-.035em`/`.98` leading, pill eyebrow, 6px gradient-topped planner card (`globals.css:13,19`; `app/page.tsx:28-45`).
5. **Coherent motion language** — `cubic-bezier(.4,0,.2,1)`, property-scoped 120–200ms, `prefers-reduced-motion` respected (`globals.css:1`).
6. **Micro-details** — mirror 6px chat tails, assistant-dot halo, dashed "stale data" pill, CSS FAQ "+"→"×", `aria-pressed` chips (`globals.css:22,25,16`).
7. **Admin pills** — best contrast management in the file, correctly mirrored both modes (`globals.css:40,43`).
8. **Light-mode footer** — deep-plum `#2a182e` slab, the single strongest color moment (`globals.css:37`).
9. **Honest legible token system** — radii/shadows/colors all tokenized in one file.

## Critical gaps (deduplicated across lanes)

### Blockers
1. **Fonts never load — entire type system renders Segoe UI.** `--font:"Inter","Fig Grotesk",system-ui,sans-serif` (`globals.css:1`) but `layout.tsx:1-9` imports only `globals.css` + leaflet; `package.json` has no font package; zero `next/font`/`@font-face`/Google link/font file (grep+glob verified). Ground truth: zero Inter faces; 800/900 weights render synthetic fake-bold. Corroborated lanes 2,5; ground-truth fact 1.
2. **Plan-page horizontal overflow from `width:100vw` full-bleed.** `.workspace-page{max-width:1500px;…;width:100vw;margin-left:calc(50% - 50vw);…}` inside `.shell` (`globals.css:25`; `layout.tsx:9`). `100vw` includes ~8px scrollbar → at 1440: scrollWidth 1407 > clientWidth 1399, map tiles to R=1434, visible scrollbar every visit. Corroborated lanes 3,4,5; ground-truth fact 2. **SEE red-team B2/N1 — the `margin-inline` recommendation does NOT fix this; verified in-browser.**
3. **Light mode resolves to 95%+ blank canvas.** White `--surface` on `--paper` (∆L≈0.008), `--line:#eae8ea` (~3.5% contrast), `--shadow-sm` 5% alpha → cards indistinguishable from page. Measured 94–96% bright, mean_sat 0.030–0.053 (`globals.css:1,10`; ground-truth §8). Corroborated lanes 1,3,4,5.

### High
4. **Maps draw in previous brand's teal/orange.** `#e4572e`/`#0f766e` at `MapView.tsx:37` (marker), `:49` (route), `RoadTripMap.tsx:15-16` (polyline + start marker). Hues 175/14 vs system 261–289. Corroborated lanes 1,4,5.
5. **Dark-mode `::selection` invisible** — lavender on lavender: `globals.css:1` `::selection{background:var(--lavender);color:var(--ink-3)}`; dark block maps both to `#cdb3ff`, no override. Code-verified.
6. **Dark-mode CTA banner is a broken light-box.** `globals.css:16` gradient + white text; no dark override; dark `.primary` (0,1,0) loses to `.cta-banner .primary` (0,2,0). Dark: lavender gradient, white text ≈1.35:1. Code-verified.
7. **Admin booking queue renders as raw text** — `admin/page.tsx:569` `<article className="offer-card">` without `.card`; `.offer-card` has no own chrome (`globals.css:28`). Still unfixed from prior audit. Code-verified.
8. **Dark footer owns first viewport of short pages.** `layout.tsx:9` mounts `<Footer/>` everywhere; `.site-footer{background:var(--ink)}` = `#2a182e` even in light (`globals.css:37`). History 37% dark, Roadtrip 31%, Login 25%. Corroborated lanes 1,5.
9. **History empty state is text-only** — `"Chưa có chuyến đi nào."` no illustration/CTA (`history/page.tsx:53-55`).
10. **Explore structurally empty; Roadtrip is an engineering form.** Explore = one search card on 1152px canvas, dom=80/text=574, no default state (`explore/page.tsx:59-67`). Roadtrip exposes lat/lng `type="number"` coordinate inputs (`roadtrip/page.tsx:56`).
11. **Every interior h1 renders 62px — per-page clamps are dead code.** `main:not(.hero)>h1` (0,1,2) beats `.explore-page>h1`, `.roadtrip-page>h1`, `.login-card h1`, `.settings-page h1`, `.admin-page>h1` (0,1,1) — all verified direct children of `<main>`. Landing hero (h1 in `.hero`) and plan title (h1 in `.trip-header`) escape. Ground truth confirms 62px sitewide, plan 50.9px. Lanes 2,3.
12. **Type scale is a bag of eyeballed sizes** — 13–20px in 1px steps, 20→44px gap, 44/46px near-duplicate h2s, emoji thumbs at 44px (same as headline), 14 sizes on plan page. Ground-truth facts 3–4.
13. **No button size scale — 4–5 fabricated heights.** Base 53px pill; forced 46px; 49px comment-form; 43px retry; `.trip-actions .icon-action{height:38px}` dead CSS (`PlanView.tsx:121` renders nine ~53px pills instead). Code-verified.
14. **`.primary{width:100%}` as base default** (`globals.css:7`) — every context opts out; footgun.
15. **`font:inherit` resets form line-height to `normal`** (`globals.css:1`) — 16px inputs render UA `normal` next to 1.5–1.55 labels.
16. **UA-default font-size leaks** — no `font-size` on `body`/`h1-h3`/`small`: body 16px implied, itinerary h3 18.72px, slot `small` 13.33px.

### Medium
17. **Dark-mode gradient collapse + token collisions** — `--brand=--lavender=--ink-3=#cdb3ff`, `--lavender-soft=--line=#352438`; violet sweep flattens (`globals.css:43`).
18. **Workspace proportions under-weight itinerary** — chat:itinerary:map ≈ 1:1.63:1.50, 16px gutters, 18px card padding vs 24px norm (`globals.css:25`).
19. **Container system inconsistent** — 1200px/24px shell on six pages vs edge-to-edge 1500px/20px on plan (`globals.css:1` vs `:25`).
20. **No space tokens; 14 hand-tuned spacing values with orphans** (18,26,15,11,38px), unexplained 56/64/72 triplet.
21. **Line-height incoherence** — five prose values (1.5/1.55/1.6/1.65/1.7) + 1.45 outlier; four eyebrow tracking dialects (.04/.07/.08/.1em).
22. **FAQ heading/content misalignment** — `.section-head` left, `.faq-list{margin:auto}` centered (~216px edge break) (`globals.css:16`).
23. **Four identical `border-top` sections**, weightless in light — no rhythm across 3095px landing.
24. **Timeline double-spacing** — `.slot` mb10 + `.timeline` gap14 ≈ 24px on plan vs 14px on history; same class different spacing.
25. **Pill+square inputs in one form; four input paddings; two tab dialects; two send-button disabled opacities (.5/.55)** (`globals.css:19,22,25,28`).
26. **Iconography is Unicode/emoji, no library** — off-center ↑↻× in circles, → as data separator across ~18 locales, mixed monochrome/color emoji on Windows.
27. **Radius governance** — Leaflet 4/3/5px chrome vs 12–24px system; same-rank boxes use 12/16/24/32px arbitrarily.
28. **Missing press states + inconsistent hover-lift** (-1/-2/-4px); three number-badge shapes (40px square/28px/30px circles).
29. **Plan header is a 9-button toolbar dump** — no hierarchy (`PlanView.tsx:121`).

### Low
30. **Dead CSS** — `.bubble.typing` (never rendered), `.trip-actions .icon-action` 38px, `.planner textarea/select`, `.nav{border-radius:0 0 0 0}`, `.text-muted` (`globals.css:4,19,22,25,43`).
31. **Unstyled native "Hủy" buttons** — `support/page.tsx:67`, `admin/page.tsx:580`.
32. **`--muted-2 #948b96` 3.04:1** for small print; dark muted/muted-2 gap nearly vanishes.
33. **Footer identity dissolves in dark mode** — `surface-2 #2a182e` on `#141014`.
34. **Chip padding varies** (9/16 vs 8/13).

## Contradictions resolved

1. **Lane 3's h1 specificity was inverted** — `main:not(.hero)>h1` (0,1,2) WINS over per-page (0,1,1). Ground truth: 62px sitewide, plan 50.9px. Lane 2 correct.
2. **Lane 5's "inconsistent h1 sizes"** lists declared (72/62/52) as rendered — they don't; all render 62px. The defect is the accidental collapse, not a visible scramble.
3. **"Dark shadows/tokens in light screenshots"** — Lane 4 resolved: dark tokens exist only inside the dark block; capture's computed styles were an emulation artifact; pixels (light) trustworthy.
4. **History's "dark block = illustration?"** — it's the global footer (`layout.tsx:9` + `globals.css:37`).
5. **Lane 4's `.primary{width:100%}` causality** with the admin bug is loose — admin bug is a missing class, unrelated.
6. **Explore footer-band anomaly** — instrumentation ambiguity, no style claim depends on it.
7. **All three "95% blank" lanes agree** — same ground-truth numbers, complementary root causes (faint separators + thin content = one blocker).

## Load-bearing claims needing follow-up verification

- Dark-mode rendering appearance (computed-style vs pixel ambiguity never resolved by a dark screenshot tied to token state).
- WCAG ratios (1.83:1, 3.04:1, etc.) are lane-computed math, plausible, single-sourced.
- `.next-build-check` artifacts carrying old `--brand:#0f766e` identity — unverified.
- Vietnamese accent clipping at `line-height:.98` in Segoe UI — plausible, unproven.
- Type-scale reconstruction as "major-third" — inference about author intent.
- Workspace proportion math + "16px gutter too tight" — taste, not measurement.
- "Segoe UI lacks 800/900" — well-known but not instrumented.
- Plan page's real photos depend on live data (`slot.anh`), not CSS.

## Prioritized recommendations

**Tier 0 — beauty-blocking**
1. Load Inter (+ Fig Grotesk) via `next/font/google` or self-hosted `@font-face`; declare `--font-inter`. `layout.tsx`, `package.json`.
2. Kill plan-page overflow — **verified fix:** remove the vw full-bleed; use `margin:0 auto;width:min(100%,1500px)` (variant B — confirmed kills scrollbar, centers) or `overflow-x:clip` (variant C — kills scrollbar but still clips map edge). Do NOT use `margin-inline:calc(50% - 50vw)` (verified no-op) or `scrollbar-gutter:stable` (verified no-op). `globals.css:25`. **Red-team corrected this; verified in-browser at 1440/1920.**
3. Route map colors through tokens: `#0f766e → var(--accent)`/`--map-line`, `#e4572e → var(--sun)`/`--danger`. `MapView.tsx:37,49`; `RoadTripMap.tsx:15-16`.
4. Dark override: `::selection{background:var(--lavender);color:var(--brand-contrast)}` in dark block. `globals.css:43`.
5. Dark override for `.cta-banner` (and `.cta-banner .primary`) with dark-safe gradient/text. `globals.css:43`.

**Tier 1**
6. Restore light-mode card separation: bump `--shadow-sm` to ~0.08 alpha + 2px Y-offset and/or darken `--line` one step; keep plum tint. `globals.css:1`.
7. Add `card` class at `admin/page.tsx:569`.
8. Resolve h1 dead-code: delete per-page clamps or raise above `main:not(.hero)>h1`. `globals.css:10,28,31,34,40`.
9. Replace `font:inherit` with `font-family:inherit;font-size:inherit;line-height:inherit`. `globals.css:1`.
10. Give `body`, `h1-h3`, `small` explicit tokenized font-sizes. `globals.css:1`.
11. History real empty state (illustration + CTA) and/or cap footer weight on short pages. `history/page.tsx`, `layout.tsx`.
12. Button size scale (`--btn-h` tokens); delete fabricated heights + dead rule. `globals.css:7,25,28,40`.
13. Remove `width:100%` from `.primary` base; add `.form-submit` utility. `globals.css:7`.

**Tier 2**
14. Resolve 44/46px h2 collision; take emoji thumbs off heading scale. `globals.css:16`.
15. Add `--space-*` tokens; normalize spacing orphans. `globals.css`.
16. Align FAQ. `globals.css:16`.
17. Widen itinerary column/gutters; named `card-dense`. `globals.css:25`.
18. Adopt an icon set; align glyphs in circles. `Planner.tsx:199`, `PlanView.tsx:127-128`, translations.
19. Style bare "Hủy" buttons. `support/page.tsx:67`, `admin/page.tsx:580`.
20. Add `:active` press feedback. `globals.css:7`.
21. Unify eyebrow family (one tracking/case). `globals.css`.
22. Consolidate prose line-heights (~1.65); loosen 13px/1.45 slot text.
23. Reduce plan toolbar: share→primary, rest→overflow menu. `PlanView.tsx:121`.
24. Hide roadtrip coordinates behind "advanced" toggle. `roadtrip/page.tsx:56`.
25. Explore imagery/empty-state anchor. `explore/page.tsx`.
26. Real destination imagery over placeholder emoji. `app/page.tsx:55`.

**Tier 3 — structural/optional**
27. De-collide dark tokens (`--brand`/`--lavender`/`--ink-3` share `#cdb3ff`); re-architect dark gradients. `globals.css:43`.
28. Keep footer a distinct dark slab in dark mode. `globals.css:43`.
29. Convert context overrides into named variants. `globals.css`.
30. Decide dark-first vs light-first; make light mode earn its color deliberately.

---

### Executive summary (~250 words)

"Mình Đi Đâu Thế" has the bones of a tasteful product but delivers about half its own ambition. The design system is genuinely well-constructed — mono-hue violet palette (261–266°) on warm paper, plum ink and plum-tinted shadows, coherent 120–200ms motion, tokenized radii, a well-engineered itinerary slot grid, and a light-mode footer that is the best color moment in the app. But beauty does not survive contact with the browser. Three blockers explain most of the gap: the fonts the design was built around (Inter/Fig Grotesk) never load — no `next/font`, no `@font-face`, no font file anywhere — so every display headline renders in Segoe UI with synthetic 800/900; light mode resolves to 95% blank near-white because white cards sit on paper with 5%-alpha shadows and hairline borders; and the flagship plan page carries a `width:100vw` full-bleed that overflows ~8px, showing a horizontal scrollbar and clipping the map (red-team verified the obvious fix doesn't work; tested alternatives in-browser). Two dark-mode defects compound it (invisible lavender-on-lavender text selection; CTA banner that stays a white-text light-box), and the maps still draw in the previous brand's teal and orange. The admin booking queue lost its card class and renders as raw text, still unfixed from the last audit. Fixing the font load, the overflow, the map colors, and the two dark-mode bugs is the single biggest beauty leap — the token layer is good enough that the app is closer to "polishable" than "rebuildable."

### Combined confidence: 8/10

Ground-truth tally: ~21 code-verified facts (map hexes at `MapView.tsx:37,49`/`RoadTripMap.tsx:15-16`; `width:100vw` at `globals.css:25`; h1 specificity verified on all seven pages; `::selection` + dark token collision; `.cta-banner` no dark override + specificity; missing `.card` at `admin/page.tsx:569`; zero font-loading mechanism; `var(--ink)` footer) + ~10 corroborating facts + ~9 externally-measured ground-truth facts (overflow geometry, pixel histograms, zero Inter faces, rendered 62px h1s, UA-default sizes, dark bands) + ~7 model-judgment items (severity rankings, page scores, taste calls). Downgrade from 9: red-team caught a no-op fix recommendation, one contradictory lane (h1) was caught by code, and subjective beauty ratings carry ±1. Upgrade consideration: every mechanically-checkable claim held, and Lane 4's emulation-caveat resolution is sound. Net **8/10**, not rounded up.
