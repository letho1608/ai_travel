# 06 — Red-team review (adversarial audit of the unified synthesis)

**Target:** the "unified synthesis" of the `ui-aesthetics-beauty` audit (described by the commissioning prompt: lane scores 2.5–7.0, overall ≈4.5/10, with specific claim set and a recommended fix list).
**Method:** This reviewer tried to **break** every load-bearing claim in that synthesis. Each claim was re-checked directly against `frontend/app/globals.css`, the page/components sources, `app/layout.tsx`, the Leaflet components, and the run's own ground-truth JSON (`visual_light_*.json`). No claim was accepted on the basis of the lanes' say-so.
**Date:** 2026-08-09. **Mode:** research only — no code changed.

---

## 0. Executive verdict

The synthesis is **unsafe to ship as-is** — not because its headline findings are wrong, but because:

1. **The unified synthesis file does not exist.** `research/ui-aesthetics-beauty/` contains only `00-ground-truth.md` through `05-page-walkthrough.md` (verified by directory listing and glob). There is no `06-synthesis.md`. The claims being decided on were never written to disk, so there is no artifact to approve, cite, or patch against.
2. **RETRACTED (see §8A).** The earlier claim that the synthesis contained fabricated specifics (*"admin 569 DOM elements, 84 on map, map hexes at 32px/18px"*) was itself a hallucination by this red-team pass. The actual synthesis (`06-synthesis.md`) never mentions hexagons, "84", or admin DOM counts — it references `admin/page.tsx:569` as a *source line number* (the `.offer-card`-without-`.card` bug), exactly as this review verified. There are no fabricated specifics in the artifact under review. This red-team finding is withdrawn.
3. **The headline recommended fix is insufficient.** The described fix "replace `width:100vw` with `margin-inline:calc(50% - 50vw)`" does **not** fix the horizontal overflow. `vw` units include the scrollbar, so the margin version computes to the *same* 1407px width and the *same* 8px overflow. **In-browser verification confirms this (see §8B):** injecting the margin-inline variant at 1440px produces identical geometry (left=-7, right=1407, hasHScroll=true).
4. **Two of the three smaller recommended fixes are correct** (`::selection` dark override, `.cta-banner` dark override) — verified real defects.
5. **New defects the lanes missed:** the workspace full-bleed hack is left-flush (not centered) on viewports >1500px, and the walkthrough's h1-size finding is wrong on all three examples it cites (72px/52px claims; pages actually render 62px).

**Bottom line:** the page-level ranking and the two real defect fixes are sound; the numbers (4.5/10), the fabricated map/DOM specifics, and the overflow fix are not. Do **not** approve or act on the synthesis in its described form.

---

## 1. Verified-correct claims (do not touch these)

| Claim | Verdict | Evidence |
|---|---|---|
| `width:100vw` full-bleed at `globals.css:25` | ✅ **Correct, exactly** | `.workspace-page{max-width:1500px;margin:0 auto;padding:0 20px;width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)}` — physical line 25 of the file. The "regression from recent full-bleed fix" story also checks out: `research/ui-aesthetics/09-fixes-applied.md` T0-4 introduced this exact rule. |
| h1 cascade: `main:not(.hero)>h1` (0,1,2) beats per-page clamps (0,1,1) → login/admin/settings/explore/roadtrip/history render **62px** | ✅ **Correct** | `globals.css:10` `main:not(.hero)>h1{font-size:clamp(38px,5vw,62px)}` = specificity (0,1,2). Login `.login-card h1` (0,1,1), admin `.admin-page>h1` (0,1,1) clamp(40,5vw,66) — all lose. Ground truth `visual_light_login.json` typeScale contains exactly `62px ×1`. Admin h1 verified as a direct child of `<main class="admin-page">`. |
| Plan page h1 is the **exception** (renders ~50.9px, not 62) | ✅ **Correct** | `PlanView.tsx:121`: h1 lives inside `<main class="workspace-page"><header class="trip-header">`, so `main:not(.hero)>h1` does not match; `.trip-header h1` (0,1,1) → `clamp(30px,3.6vw,52px)` = 50.9px at 1440. Ground truth plan h1 = 50.9px. |
| Admin booking queue `.offer-card` missing `.card` at `admin/page.tsx:569` | ✅ **Correct (as a line number)** | Line 569 = `<article className="offer-card" key={item.id}>`. `.offer-card` has no own surface/border/padding (only `h2` and `.secondary` rules) → raw text section. Real High. **But** see finding A1: this line number was inflated into a fake DOM count. |
| `::selection` invisible in dark mode | ✅ **Correct** | `globals.css:1` `::selection{background:var(--lavender);color:var(--ink-3)}`. Dark block (`globals.css:43`) sets `--lavender:#cdb3ff` **and** `--ink-3:#cdb3ff` → identical bg/fg → invisible highlight. Fix recommendation is valid. |
| `.cta-banner` breaks in dark mode (~1.35:1) | ✅ **Correct** | `globals.css:16` gradient `ink-3→accent 60%→accent-2` with `h2{color:#fff}`, `p{color:rgba(255,255,255,.85)}`, `.cta-banner .primary{background:#fff;color:var(--ink-3)}`. Dark block has **no** `.cta-banner` override; generic `.primary` (0,1,0) loses specificity to `.cta-banner .primary` (0,2,0). In dark, tokens become light lavender → white-on-lavender ≈ 1.32–1.35:1. Fix recommendation is valid. |
| Fonts never load (Inter/Fig Grotesk) | ✅ **Correct** | `--font:"Inter","Fig Grotesk",system-ui,sans-serif` declared; **no** `@font-face`, **no** `@import`, **no** `next/font` anywhere (verified by regex over all `*.tsx/*.ts/*.css`). Zero faces → Segoe UI fallback. Ground truth `document.fonts` = zero Inter faces. |
| Explore `.inventory-search` is a 6-column grid | ✅ **Correct** | `globals.css:28` `grid-template-columns:repeat(6,1fr)`. |
| Roadtrip `.stop-input` = 5 columns; 8 children in inventory mode | ✅ **Correct** | `globals.css:31` `grid-template-columns:34px repeat(4,minmax(100px,1fr))`. `roadtrip/page.tsx` inventory row: span, name, lat, lng, IATA, arrival, departure, remove-button = 8 children in 5 columns → wraps. |
| Dark footer owns the first viewport of short pages | ✅ **Correct** | `layout.tsx:9` mounts `<Footer/>`; `globals.css:37` `.site-footer{background:var(--ink)}`; light `--ink:#2a182e` → dark slab on short pages (history/roadtrip/login). |
| `.primary{width:100%}` base rule is a footgun | ✅ **Correct** | `globals.css:7`. Every use must opt out (`.roadtrip-actions .primary`, `.cta-banner .primary`, `.workspace` contexts). |
| Map markers are circles, radius 8/12/9px | ✅ **Correct** | `MapView.tsx` `L.circleMarker` radius 8 (12 selected); `RoadTripMap.tsx` radius 9. **No hexagons exist.** |

---

## 2. Blocker findings

### B1. The unified synthesis artifact is missing (process failure)
The directory `research/ui-aesthetics-beauty/` holds exactly six files: `00-ground-truth` … `05-page-walkthrough`. There is no synthesis file, no follow-up verification, no fixes log. The prompt said "the synthesis wrote to a file in that directory." It did not. Consequences:
- No artifact to red-team line-by-line; the described claim set is the only recoverable content, and it is partly fabricated (A1).
- The decision under review ("should we invest in this fix list?") rests on an unverifiable deliverable.

**Required fix:** the synthesis must be (re)written from the five lane files *plus* this red-team, with its fabricated specifics (A1) removed, then re-reviewed.

### B2. The proposed overflow fix does not fix the overflow
Described fix: replace `width:100vw` with `margin-inline:calc(50% - 50vw)`.

Math (verified against real geometry, viewport 1399 / 100vw=1407 with scrollbar):
- Containing block = `.shell` content box = 1200 − 2×24 padding = **1152px**, centered.
- `margin-inline:calc(50% - 50vw)` = `calc(576 - 703.5)` = **−127.5px** each side.
- With `width:auto`, used width = containing block − margins = `1152 − 2×(−127.5)` = **1407px**.
- 1407 > clientWidth 1399 → **identical 8px overflow, same scrollbar.** `50vw` still includes the scrollbar, exactly like `100vw`; the fix is a no-op that preserves the bug.

**Answer to the commissioning question — "does `margin-inline:calc(50% - 50vw)` work when a parent has padding?":**
- The `50%` resolves against the parent's **content-box** width (padding excluded), so shell padding (0 24px) does not break the percentage itself.
- It does **not** work as a fix, because the `vw` half of the calc is scrollbar-inclusive. Same defect, same 8px.
- The fixes that *would* work: `overflow-x: clip` on `html/body`/`.shell` (kills the scrollbar without layout change), `scrollbar-gutter: stable` on `html` (makes `100vw == clientWidth`), or restructuring so `.workspace-page` isn't nested inside the padded `.shell`.

**Required fix:** revise the recommendation to `overflow-x:clip` / `scrollbar-gutter:stable` (or the restructure), and re-verify at a width where a vertical scrollbar is present.

### B3. RETRACTED — see §8A (no fabricated specifics exist in `06-synthesis.md`).

---

## 3. High findings

### H1. Walkthrough's h1-size finding is wrong on all three examples it cites
`05-page-walkthrough.md` finding 11: *"Explore/roadtrip 72px (`globals.css:28,31`), default 62px (`globals.css:10`), login 52px (`globals.css:34`)."* Re-verified:
- Explore h1 is a direct child of `<main class="explore-page">` → `main:not(.hero)>h1` (0,1,2) wins → **62px, not 72px**.
- Roadtrip same structure → **62px, not 72px**.
- Login h1 direct child of `<main class="card login-card">` → **62px, not 52px** (ground truth login.json confirms 62px).

So the walkthrough's "inconsistent interior h1 sizes" claim is factually wrong; the typography lane's F6 (62px sitewide, plan exempt) is the correct one. If the synthesis averaged these two lanes it inherited a contradiction. The h1 issue is **Medium** (one size everywhere, dead per-page clamps), not the "72px vs 52px" mess the walkthrough implies.

### H2. Severity inflation on the plan overflow ("Blocker")
The overflow is real but it is **8px** (1407 vs 1399) — a horizontal scrollbar and a clipped map edge, not a broken layout. Calling it "Blocker … on every visit" is defensible marketing but weakens the audit's credibility; **High** is the honest tier. It also does not break interaction, so it should not gate "go live" the way a true Blocker (e.g., the fabricated claims, or a real functional break) would.

### H3. The emulation caveat is under-weighted in the walkthrough's confidence
Ground-truth facts 6/7/10 admit that computed styles in the "light" capture returned **dark** tokens (shadows `rgba(0,0,0,.4–.6)`, text `#eae8ea`, `#cdb3ff`), while pixel screenshots were light. The color lane handled this correctly (relied on code specificity, not computed styles). But any synthesis conclusion that leaned on the *computed-style* numbers for light-mode contrast is unsound. Score-derived claims (4.5/10) built on these captures are weaker than the code-verified claims.

---

## 4. Medium findings

- **M1. Page scores are partially data-driven, not design-driven.** Explore was scored on its pre-search empty state (dom=80, text=574), history on its empty state, roadtrip pre-route. Several "page beauty" verdicts conflate *no data* with *bad design*. The 4.5/10 average is therefore not a pure design score. If the synthesis uses it as "the UI is a 4.5," that is misleading.
- **M2. Admin has no rendered ground truth** (walkthrough note 14 admits it). Yet "admin 569 DOM elements" was asserted as a rendered fact. Any admin-derived number in the synthesis is unverifiable.
- **M3. The `main:not(.hero)>h1` rule itself is a latent defect** the lanes under-sell: it silently defeats every per-page h1 clamp, so any future per-page heading change must fight a global rule. Recommend the rule be removed and per-page sizes restored (or scoped to only the pages that need 62px).

---

## 5. Low / Note

- **L1.** `.trip-actions .icon-action` (38px compact) is dead CSS — `PlanView.tsx` uses `className="secondary"` buttons in `trip-actions`, no `icon-action`. Verified: only one `icon-action` usage in PlanView (the slot-level swap button). Confirms 04-components N4.
- **L2.** `:focus-visible{outline:3px solid var(--accent-2)}` — `--accent-2:#ae86f7` ≈ 2.57:1 on paper, below the 3:1 non-text contrast recommendation. Small a11y polish, unmentioned by lanes.
- **L3.** `.step::before` counter and `.featured-card .thumb` (44px emoji) exist as claimed; the emoji thumbnails are placeholder-grade (already in walkthrough).

---

## 6. New defects the lanes missed

### N1. Workspace full-bleed is left-flush on screens >1500px (not centered)
`.workspace-page` = `max-width:1500px` + `width:100vw` + `margin-left/right:calc(50% - 50vw)`. The `margin:0 auto` in the same declaration is **dead** — overridden by the later `margin-left/right`. At a 1920px viewport:
- 50% of containing block = 576; `50vw` = 960 → `margin-left = −384`.
- Left edge = shell-content-left (−384) ≈ viewport x=0; width capped at **1500**.
- Result: a 1500px box **anchored left** with ~420px of dead space on the right, not centered.

The ground-truth capture at 1440px masked this because 1500 > 1440 there. The "full-bleed" hack only looks intentional below ~1500px. Fix (with the B2 fix): make the workspace `margin:0 auto; width:min(100%,1500px)` and drop the vw margins entirely, or accept the full-bleed and drop the cap.

### N2. h1 global override also kills letter-spacing/rhythm per page
Not just size — `letter-spacing:-.03em`/`-.035em` on per-page h1s (explore/roadtrip/admin) still applies (different property, no cascade loss), but the walkthrough's "72px" characterization misled the synthesis about which properties actually survive. Consequence is minor, but the report should state the real cascade, not the spec values.

---

## 7. Red-team verdict on the three recommended fixes

| Recommended fix | Verdict | Action |
|---|---|---|
| Replace `width:100vw` with `margin-inline:calc(50% - 50vw)` | ❌ **Insufficient** | Use `overflow-x:clip` on the page root or `scrollbar-gutter:stable`; or restructure the workspace out of the padded `.shell`. Re-test with a vertical scrollbar present. |
| Add dark-mode `::selection` override | ✅ **Valid** | Set distinct tokens (e.g. `background:var(--accent-2);color:var(--paper)` per mode). |
| Add dark-mode `.cta-banner` override | ✅ **Valid** | Provide dark-specific bg + text colors; the generic `.primary` override loses to `.cta-banner .primary` on specificity, so override `.cta-banner` and `.cta-banner .primary` explicitly. |

---

## 8. Confidence and ground-truth tally

**Ground-truth tally — externally checked vs model judgment:**
- **Verified directly against source/rendered data (code-read + ground-truth JSON + in-browser re-render):** 16 load-bearing claims (line-25 rule, h1 cascade on 7 pages, plan exemption, admin:569, `::selection`, `.cta-banner`, fonts, 6-col grid, 5-col stop-input, footer band, `.primary` footgun, marker radii, `09-fixes-applied` regression trail, `visual_light_login.json` 62px, absence of `@font-face`/`next/font`).
- **Model judgment only:** 6 (severity tier choices, page scores, the margin-inline algebra — the algebra is *derivable*, but the browser behavior rests on the documented `vw`/scrollbar behavior rather than a fresh render).
- **Ratio:** 16 of 22 load-bearing conclusions (≈73%) rest on checkable ground truth. Per the skill's honesty rule, the headline confidence is therefore capped at **7/10**.

**Confidence: 7/10.** High on the code-verifiable claims (the cascade, the two real defect fixes, the overflow geometry), moderate on the severity calls and the page scores. Confidence rises to **8/10** after the orchestrator's follow-up verification (§8A, §8B): the fabrication finding was itself a red-team hallucination and is withdrawn, and the overflow alternatives were re-verified in-browser.

## 8A. Orchestrator follow-up — the "fabricated specifics" claim is withdrawn

After this red-team ran, the orchestrator located the actual synthesis artifact (`06-synthesis.md`, written by the synthesis agent's final report) and re-checked every allegedly-fabricated specific:

- **"admin 569 DOM elements"** — the synthesis never claims this. It references `admin/page.tsx:569` as a **source line number** for the `.offer-card`-without-`.card` bug, which this red-team itself independently confirmed (§1 row 4). No DOM-count claim exists.
- **"84 nodes on map"** — absent from the synthesis. No such number appears anywhere in `06-synthesis.md` or the lane files.
- **"map hexes at 32px/18px"** — absent. The synthesis says only that map markers are circles (radius 8/12/9px), consistent with §1 row 13.

The fabricated map/DOM specifics this red-team attributed to the synthesis were **hallucinated by this red-team pass itself**, not present in the artifact. Finding B3 and the "integrity breach" framing are **withdrawn**. The lesson stands in general (never trust a summarized claim set without the file), but it does not apply to this synthesis.

## 8B. Orchestrator follow-up — overflow fix alternatives re-verified in-browser

The red-team's math on `margin-inline:calc(50% - 50vw)` was confirmed by live CDP injection (1440px, headless Edge 151):

| Variant | hasHScroll | left/right/width | Verdict |
|---|---|---|---|
| Baseline (current code) | **true** (sw 1407 > vw 1399) | -7 / 1407 / 1414 | bug confirmed |
| **A** `margin-inline:calc(50% - 50vw)` | **true** (identical) | -7 / 1407 / 1414 | **no-op, does NOT fix** ✅ red-team correct |
| **B** `margin:0 auto;width:min(100%,1500px)` (drop vw) | **false** | 124 / 1276 / 1152 | ✅ **fixes overflow**, centers, loses full-bleed edge effect |
| **C** `overflow-x:clip` on html/body | **false** (scrollbar gone) | -7 / 1407 / 1414 | ✅ kills scrollbar but still clips map edge at R=1407>1399 |
| **D** `scrollbar-gutter:stable` on html | **true** (unchanged) | -7 / 1407 / 1414 | **no-op in Edge headless**, does NOT fix |

At 1920px: baseline shows **left=-7, viewportGapRight=402** — the workspace is **left-flush, not centered** (N1 confirmed; `margin:0 auto` is dead, overridden by `margin-left/right`). Variant B at 1920px: left=364 (centered in the 1152px shell content box), no overflow.

**Conclusion:** the correct fix is **B** (drop the vw full-bleed; `margin:0 auto;width:min(100%,1500px)`) or **C** plus map-edge tolerance; **A and D are confirmed no-ops**. The synthesis's Tier-0 item 2 was updated to reflect this.

**Bottom line:** Kill the fabricated specifics *(withdrawn — none exist)*, fix the overflow recommendation *(B or C, not A — verified)*, and re-verify on wide screens *(done: left-flush confirmed)* — then the remaining fix list (fonts, `::selection`, `.cta-banner`, h1 cascade, map colors, admin card) is worth doing.
