# 05 — Page-by-Page Beauty Walkthrough

**Lane:** PAGE-LEVEL VISUAL APPEAL (aesthetics only, not functionality)
**Analyst:** Agent 5 / beauty walkthrough
**Method:** Combine rendered pixel ground truth (`00-ground-truth.md`, captured 2026-08-08 at 1440x1000, viewport ≈1399x873, Edge 151 CDP) with full source + `globals.css` reading. I cannot view the screenshot images directly; pixel facts below are the recorded ground truth, and every layout claim is cross-checked against the CSS/JSX.

**Global facts that apply to ALL pages (kept brief — atom lanes own the detail):**
- Every page renders inside `<div className="shell">` followed by `<Footer/>` (`app/layout.tsx:9`). The footer's `.site-footer` background is `var(--ink)` = `#2a182e` (dark plum) **even in light mode** (`globals.css:37`). This is the identity of every "dark band" discussed below.
- `--font: "Inter","Fig Grotesk",system-ui,sans-serif` is declared (`globals.css:1`) but **zero Inter/Fig Grotesk font faces are ever loaded** (ground-truth fact 1). All text renders in Segoe UI. This is a page-level ceiling on every screen.
- Light theme is extremely low saturation: paper `#f7f6f3` body, mean_sat 0.030–0.053 across pages (ground-truth facts 6–8). The plum/lavender brand appears only in small accents; the big brand-colored elements are the buttons, stop-number circles and the footer.

---

## Score table (0–10, page-level first-viewport beauty + overall impression)

| Page | Score | One-line verdict |
|---|---|---|
| Landing `/` | **7.0** | The only page that feels consciously designed — but held back by font failure and near-zero color. |
| Plan workspace `/plan/[token]` | **6.5** | Richest, most "real product" page (photos + map + chat), wounded by a horizontal-overflow bug and a 9-button toolbar. |
| Settings `/settings` | **5.0** | Tidy, clean, unremarkable; the design system applied but nothing delights. |
| Login `/login` | **4.5** | Respectable minimal auth card, but sparse and footer-crashed on first viewport. |
| Admin `/admin` | **4.5** | Genuinely coherent for an internal console (cards, pills, status colors), but zero "beauty" ambition. |
| Explore `/explore` | **3.5** | 96% white first viewport; a dense raw input-grid with no imagery and no result anchor. |
| Roadtrip `/roadtrip` | **3.0** | Consumer feature dressed as an engineering form (lat/lng/IATA boxes); dark footer owns 31% of first viewport. |
| History `/history` | **2.5** | Worst in the app: text-only empty state, and the dark footer swallows ~37% of the first screen. |

Average **4.6** — the app reads as "functional-first, designed-last."

---

## 1. Landing `/` — score 7.0

**Rendered facts:** 95.2% bright, mean_sat 0.036, top color `#e0e0e0` at 94.6%; scrollHeight 3095px (long page); dom=139, text=1658px; hero type scale includes one 88px and 44/46px headings with a 20→44px gap (ground-truth facts 3, 8).

**Structure** (`app/page.tsx`): a hero section (`page.tsx:28-45`) with eyebrow pill, a two-line `h1` ("Đi đâu / để mình lo"), lead, and a social-proof line; a `Planner` card on the right (`components/Planner.tsx`). Below: three featured-destination cards (`page.tsx:52-63`), three numbered "how it works" steps (`page.tsx:71-78`), an FAQ accordion (`page.tsx:87-95`), and a gradient CTA banner (`page.tsx:98-108`).

**What is genuinely good (above the fold):** The hero is the app's single strongest visual anchor. `globals.css:13` gives `h1` `clamp(48px,6.5vw,88px)` with `line-height:.98` and `letter-spacing:-.035em` — a real display headline. The eyebrow is a pill (`padding:8px 16px; border-radius:full; background:var(--lavender-soft)`), not a bare uppercase label, which shows craft. The Planner card is the second anchor: it gets a 6px brand-gradient top edge (`globals.css:19 .planner::before`), a chat welcome bubble, quick-action chips, and a pill chat input. As a two-column composition (display headline ‖ functional planner) it is a legitimately well-thought hero.

**What drags it down:**
- The 88px hero is magnificent in theory and ordinary in practice, because the font never loads. An 88px Segoe UI "Đi đâu" is not a brand moment; it is a wall of system text.
- Near-monochrome: 95.2% of the frame is bright with saturation 0.036. The lavender appears only in the eyebrow pill, the planner top bar, chips and accents. A travel product's hero should feel warm/hungry for a place; this one is pale.
- Emoji thumbnails: the three featured cards use a `<div class="thumb">☕/🍜/🏛️</div>` on a lavender gradient (`app/page.tsx:55`, `globals.css:16`). For a trip-planning brand whose differentiator is *verified real destinations*, placeholder-grade emoji tiles read as unfinished. Travel sites win on photography; this has none.
- Type-scale flaws: no size between 20px and 44px, and 44px section headings coexist with a near-identical 46px step heading (`globals.css:16 h2 clamp(30,4vw,46)`) — two competing "section title" voices (ground-truth fact 3).
- 3095px of page height with only five sections; the section blocks are tall and airy, and the pixel map shows mostly empty paper between content clusters.

**Above the fold:** strong — two anchors (headline + planner card). This is what lifts the score to 7 despite the flaws.

---

## 2. Plan workspace `/plan/[token]` — score 6.5

**Rendered facts:** 90.4% bright but mean_sat 0.053 (the highest of any light page — the map and photos add color); scrollWidth 1407 > clientWidth 1399 **= horizontal overflow**; `main.workspace-page` bounding L=-7 R=1407 while viewport vw=1399; Leaflet map tiles extend to R=1434 (ground-truth fact 2); dom=252, text=4377 (richest page); 14-step type scale, no modular rhythm (fact 4).

**Structure** (`components/PlanView.tsx`): trip-header (`PlanView.tsx:121`) with eyebrow, big `h1`, summary paragraph, and **nine** action buttons; a `trip-facts` pill row (`PlanView.tsx:122`); then a three-column workspace (`PlanView.tsx:127-129`): chat assistant panel | day-tabbed itinerary timeline | Leaflet map + legend.

**Strengths — this is the app's "money page":**
- It is the only page whose first viewport is *about real content*: itinerary slots with real photos (`PlanView.tsx:118`, `globals.css:25 .slot-photo` 150px cover images), a live map with teal/orange route markers (`MapView.tsx:37,49` — teal `#0f766e`, selected-orange `#e4572e`), day tabs, fact pills, a chat. That is why saturation is highest here; the map tiles and photos carry the whole app's color budget.
- The slot cards are well-crafted: numbered stop-index circle, time column, photo band, cost line, source link, hover lift and a selected-state ring (`globals.css:25`). The timeline + map + chat trio genuinely communicates "planning workspace."
- The `trip-facts` pill row (`globals.css:25`, lavender-50 chips) is a nice micro-moment.

**Defects:**
- **Horizontal overflow (Blocker — full analysis in §8):** `globals.css:25` `.workspace-page{...width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)}`. `100vw` includes the scrollbar (~8px) and `vw > clientWidth`, so the page is 8px too wide: L=-7, R=1407 vs 1399 viewport, map tiles to 1434. Result: an unwanted horizontal scrollbar on the flagship page and a right-edge clip of the map. The full-bleed fix that produced this traded one bug for another.
- **Toolbar dump:** nine `secondary` buttons in `trip-actions` (`PlanView.tsx:121`): share, download PDF, add calendar, download JSON, comments, feedback, versions, undo, regenerate. Nine identical outline pills is not hierarchy; it is a wall of chrome competing with the headline. Share should be primary; the rest belong in an overflow menu.
- Dense type scale (14 steps, 10→50.9px, no rhythm) and a huge DOM (252 nodes) make the page feel busy rather than composed.

**Above the fold:** a big trip title + fact pills + three panels. There IS a strong functional anchor, but the visual anchor is the overloaded header rather than the content.

---

## 3. Explore `/explore` — score 3.5

**Rendered facts:** 96% bright, mean_sat 0.030 (least color in the app), "≈1 small content cluster" in the ASCII map; dom=80, text=574 — the thinnest page by text alongside history.

**Structure** (`app/explore/page.tsx:59-64`): eyebrow + two-line `h1` (`clamp(42,5.5vw,72px)`, `globals.css:28`) + lead + four tab pills (flight/hotel/activity/transfer) + a `card` search form (default flight tab: origin/destination/departure/return/adults + submit). No results in initial state. Hotel tab adds lat/lng/radius/price fieldsets (`page.tsx:62`).

**Assessment:** On load this is a near-empty white page. The header h1 is genuinely big, but the rest of the first viewport is a dense 6-column grid of labeled inputs (`globals.css:28 .inventory-search{grid-template-columns:repeat(6,1fr)}`) — origin, destination, dates, adults — rendered as a bare strip of boxes. There is no imagery, no results, no map, no price tease. The "1 small content cluster" pixel reading is exactly right: a header and a form floating on empty paper.

**Why it scores low:** the page is *functional-only*. For a page whose job is "find flights/stays," the first impression is a form, not an offer. The h1 is a lone anchor; the form is dense; the tabs are fine but generic. Even the working state (offer cards with a big price `h2`) is decent, but the *beauty audit* scores what a user first sees, and a first-time visitor sees white + inputs. It also has the sharpest h1/body mismatch in the app (72px display h1 vs 13px form labels).

**Above the fold:** weak. A giant h1, then raw controls. No image, no gradient, no illustration.

---

## 4. Roadtrip `/roadtrip` — score 3.0

**Rendered facts:** 66.5% bright, 31.5% dark (the dark is the footer + dark-plum index circles/button; the map only appears after a route is generated); dom=86, text=610.

**Structure** (`app/roadtrip/page.tsx:56`): eyebrow + `h1` (72px) + lead + a `roadtrip-builder card` with a stop editor — per-stop rows of `34px repeat(4,minmax(100px,1fr))` columns (`globals.css:31 .stop-input`) holding a numbered circle, stop name, **latitude**, **longitude**, and (in inventory mode) IATA code, arrival and departure dates — plus add-stop, round-trip toggle, inventory toggle, and a build button. `RoadTripMap` renders only after a successful route.

**Assessment:** The cardinal beauty sin here is that a consumer-facing "road trip" feature exposes *coordinate inputs*. `app/roadtrip/page.tsx:56` puts `type="number"` lat/lng fields (plus IATA codes, arrival/departure dates) in the main builder. That is an engineering tool, not a travel product — "beauty from the user's eye" is destroyed by asking a vacationer to type `20.2506, 105.9745`. The numbered stop circles are the one branded flourish; otherwise it is rows of raw inputs, a 72px h1, and a dark footer taking ~31% of the first viewport. The result state (map + summary cards, `roadtrip-summary`/`roadtrip-map` 580px) is far more attractive — but it is hidden behind the form gate.

**Above the fold:** moderate. Big h1 + a form card; no imagery; the builder rows dominate.

---

## 5. History `/history` — score 2.5

**Rendered facts:** 62% bright, **37% dark** — the largest dark band of any page; dom=64, text=359 (the smallest page in the app); ASCII map shows rows 8–10 as solid `██▓` blocks.

**Investigation of the dark band (the headline finding):** The ground-truth hypothesized this was "an empty-state illustration." **It is not. It is the footer.** `app/history/page.tsx:55` renders only: eyebrow + `h1` + (if any) notifications + a status line (`plansLoading ? loading : planError ? loadFailed : plans.length===0 ? noTrips : ""`) + an empty `.timeline`. With no data, the content is ~150–250px tall. The layout wrapper (`app/layout.tsx:9`) then drops in `<Footer/>`, whose `.site-footer` is a **solid dark-plum `#2a182e` block** (`globals.css:37`, `background:var(--ink)`) with `margin-top:72px` and rounded top corners. In a 873px-tall viewport, that dark block occupies roughly the bottom third to 40% of the first screen. Hence 37% dark pixels. The same mechanism explains roadtrip 31.5% and login 25% (pages with short content).

**Assessment:** This is the app's worst first viewport: a big h1 ("Lịch sử của bạn"), one gray line ("Chưa có chuyến đi nào."), and then a cliff-edge into a wall of dark plum. No illustration, no icon, no "Create your first trip" CTA, no motion — a text-only empty state (`history/page.tsx:53-55`) that also happens to be the *default* state for every anonymous visitor. A dark footer that is gorgeous on a long, content-rich page is a catastrophe on a 64-node page.

**Above the fold:** none. There is no visual anchor below the h1; the anchor is accidentally the footer.

---

## 6. Settings `/settings` — score 5.0

**Rendered facts:** 94.3% bright, mean_sat 0.036; dom=104, text=716; no dark-band issue (content fills the viewport).

**Structure** (`app/settings/page.tsx:37`): a single centered `.settings-page.card` (`max-width:620px`) with eyebrow + `h1` + status line + a form of three stacked selects (language/currency/units) + save, then a danger zone (red `h2`, delete button, typed-confirmation gate `XOA TAI KHOAN`).

**Assessment:** Clean, correct, and instantly forgettable. The card is well-centered, the labels are bold, the select styling matches the system (`globals.css:34`). The danger zone is honestly the best-designed thing on the page (red heading, clear confirmation flow). But nothing here delights: no imagery, no grouping beyond the bare card, no brand moment. It is the benchmark "system-applied, no-soul" page — hence a neutral 5.

**Above the fold:** acceptable — a real card with a form, nothing broken, nothing memorable.

---

## 7. Login `/login` — score 4.5

**Rendered facts:** 72.5% bright, 25% dark (footer below the card); dom=69, text=636.

**Structure** (`app/login/page.tsx:64-75`): a centered `.login-card` (`max-width:600px`, `globals.css:34`) with eyebrow + `h1` ("Giữ mọi hành trình ở một nơi.") + lead + a consent checkbox + (after consent) the Google Sign-In button; error states otherwise.

**Assessment:** A respectable minimal auth card — centered, generous padding, a nice headline, progressive disclosure of the Google button. But: no brand mark/logo, no illustration or side panel, and in a 873px viewport the dark footer claims ~25% of the frame. The consent-first gating means the first thing a user sees is a checkbox and two legal links, which is visually unexciting (functionally correct). It reads as "undesigned-but-neat" rather than "branded." 4.5.

**Above the fold:** moderate. The headline is a reasonable anchor; the Google button (once consent is ticked) is a strong recognizable element.

---

## 8. Admin `/admin` — score 4.5 (from code — not in the rendered capture set)

**Structure** (`app/admin/page.tsx`): an admin-token login form, then a large dashboard: `admin-strip` stat cards, a two-column `admin-grid` (provider readiness, diagnostics, counters, limits, AI quality), plus AI usage, maintenance, data quality, catalog search, plans, users, booking-support queue, and event audit log (`admin/page.tsx:355-604`).

**Assessment:** For an internal console this is genuinely well-sheeted: consistent cards, status pills with semantic colors (`admin-pill.ready` green / `.mock` amber / `.missing_credentials` red — `globals.css:40`), metric grids, responsive table-like row grids. It is the same design language as the consumer app, which is a credit to system discipline. But it has no aesthetic ambition and none of the delight the consumer pages attempt. First viewport is a plain token form. 4.5 is fair — good tool, not beautiful.

**Above the fold:** a big h1 + a login form card; purely functional.

---

## Cross-page investigations

### 8. The dark bands at the bottom of light-mode screenshots — RESOLVED
Every light-mode page with short content shows a large dark block in viewport rows 8–10:
- history **37%** dark, roadtrip **31%**, login **25%**; explore/settings/landing show ~94–96% bright because their content is tall enough (landing 3095px) to push the footer below the fold — or, for explore, the footer fell outside the captured region (see note below).

**Cause (confirmed in code, not an empty-state illustration):** `app/layout.tsx:9` mounts `<Footer/>` on every route. `globals.css:37` `.site-footer{background:var(--ink);color:var(--lavender);border-radius:var(--radius-xl) var(--radius-xl) 0 0;padding:56px 24px 24px}`. In light mode `--ink` = `#2a182e` (`globals.css:1`). The footer is therefore a **rounded-top, solid dark-plum slab** rendered on a light paper body — a deliberate design choice that looks intentional on the landing page's long scroll but reads as a bug on short pages.

**Page-level verdict:** This is a **High** finding. On the three shortest pages the first-viewport composition is "white strip / dark slab" — the least harmonious two-tone possible, and it directly inflates the measured darkness (history 37%, roadtrip 31%, login 25%). A dark footer is fine; a dark footer that owns 40% of the *first screen* of a page that has almost nothing else is a beauty defect. (Fix belongs to layout/color lanes: e.g., cap footer on short pages, or give those pages empty-state content tall enough to absorb it.)

*Note on explore:* the capture shows 96% bright with no footer band, yet explore's content (h1+lead+tabs+form ≈ 550–600px) should place the footer within an 873px viewport. Either the explore capture region clipped the footer or the form rendered shorter than estimated. This is a minor instrumentation ambiguity, not a styling claim; it does not change explore's page score.

### 9. Plan-page horizontal overflow — RESOLVED (Blocker)
**Cause:** `globals.css:25`:
```css
.workspace-page{max-width:1500px;margin:0 auto;padding:0 20px;width:100vw;
  margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)}
```
`width:100vw` uses the *viewport width including the vertical scrollbar* (~1407px), while the layout viewport's clientWidth is 1399px. The centering trick then shifts the element left by `(50% - 50vw)` and its right edge lands at R=1407, 8px past the edge; the Leaflet map tiles extend to R=1434. Result: `scrollWidth 1407 > clientWidth 1399` → a visible horizontal scrollbar on the app's flagship page, plus a 7px leftward shift (L=-7).

**Damage to polish:** Real but bounded. It is ~8px of overflow — not a layout breakage — but (a) it introduces a horizontal scrollbar where users expect none, which on a 3-panel tool reads as sloppiness; (b) the map's right edge is clipped, so the "selected place" popup at the rightmost point can be cut off; (c) it is a regression introduced by the recent full-bleed fix, i.e. a known trade-in of bugs. Page-level, it knocks the workspace from "polished product" toward "works-in-progress." **High/Blocker** because the flagship page of the product has a visible scroll defect on every visit.

### 10. Above-the-fold audit per page
| Page | Anchor present? | Quality |
|---|---|---|
| Landing | Yes — 88px hero + planner card | Strong |
| Plan | Yes — big trip title + fact pills | Strong but crowded by 9-button bar |
| Explore | Partial — 72px h1 only | Weak |
| Roadtrip | Partial — h1 + form | Weak |
| History | No | None (footer becomes the anchor) |
| Settings | Yes — h1 + card | Moderate |
| Login | Yes — h1 + card | Moderate |
| Admin | Yes — h1 + form | Moderate |

### 11. Light vs dark: a note
The dark-mode capture (landing 94.9% dark, `#c0a0e0` lavender accents on pure black) reads far more *like the brand* than light mode. The evidence — brand color `--ink` is a near-black plum, the footer is permanently dark, buttons are dark in light mode, and dark shadows/tokens appeared in the light-mode computed-style capture (ground-truth facts 6, 7, 10) — suggests this product is **dark-mode-first** and light mode is the afterthought. The light theme's mean_sat 0.03–0.05 wash is the direct consequence. Page-level takeaway: every light-mode page is graded against a palette the design doesn't actually believe in.

---

## Findings (categorized)

**Blocker**
1. **Plan workspace horizontal overflow.** `globals.css:25` (`width:100vw` + `margin-left:calc(50% - 50vw)` + `margin-right:calc(50% - 50vw)`) → `scrollWidth 1407 > clientWidth 1399`, `main.workspace-page` L=-7 R=1407, map tiles to R=1434. Visible horizontal scrollbar + clipped map edge on the flagship page every visit.
2. **Fonts are declared but never loaded.** `globals.css:1` (`--font:"Inter","Fig Grotesk",...`) but zero faces load (ground-truth fact 1). Every display moment — 88px landing hero, 72px interior h1s, 50.9px plan title — renders in Segoe UI. This single defect caps the entire app's aesthetic ceiling and defeats the type-scale system the other lanes found.

**High**
3. **Dark footer dominates short pages' first viewports.** `app/layout.tsx:9` + `globals.css:37` (`.site-footer{background:var(--ink)}`). History 37% dark, roadtrip 31%, login 25% in light mode — a wall of dark plum at rows 8–10 of a near-empty screen. On history it is the *default* state (anonymous visitors).
4. **History empty state is text-only.** `app/history/page.tsx:53-55` renders one `lead` ("Chưa có chuyến đi nào.") with no illustration, no CTA. Combined with finding 3, the default History first viewport is "h1 + one gray line + giant dark slab."

**Medium**
5. **Roadtrip exposes raw coordinates to consumers.** `app/roadtrip/page.tsx:56` puts lat/lng number inputs (plus IATA/date fields in inventory mode) in the primary builder. Kills the travel-product illusion; reads as an internal tool.
6. **Explore's first viewport is a form, not a product.** `app/explore/page.tsx:59-64`; 96% bright, one content cluster. No imagery, no result anchor; dense 6-col input grid (`globals.css:28`).
7. **Plan header is a 9-button toolbar dump.** `PlanView.tsx:121` `trip-actions` — share/downloadPDF/calendar/downloadJSON/comments/feedback/versions/undo/regenerate as nine equal outline pills, no hierarchy.
8. **Near-zero color in light mode.** mean_sat 0.030–0.053 across all pages; lavender only in small accents. The light theme feels washed out; dark mode (`#c0a0e0` on black) is where the brand actually lives.
9. **Landing type scale defects.** No size between 20px and 44px; 44px and 46px section headings compete (ground-truth fact 3; `app/page.tsx` + `globals.css:16`).

**Low**
10. **Emoji thumbnails on landing featured cards.** `app/page.tsx:55` (`☕🍜🏛️` on gradient) — placeholder-grade imagery for a travel brand.
11. **Inconsistent interior h1 sizes.** Explore/roadtrip 72px (`globals.css:28,31`), default 62px (`globals.css:10`), login 52px (`globals.css:34`) — no single interior title scale.
12. **Login first screen is a legal checkbox.** `app/login/page.tsx:69` — consent before the Google button means the visual anchor is a checkbox, not sign-in.

**Note**
13. Explore capture's missing footer band is an instrumentation ambiguity (see §8 note); doesn't change the score.
14. Admin has no rendered ground truth; scored from code at 4.5.

---

## Best and worst pages (with evidence)

**Best — Landing (7.0).** It is the only page with a deliberate above-the-fold composition (display headline ‖ planner card, `app/page.tsx:28-45`), and it carries the most craft details per square inch: pill eyebrow, gradient-topped planner card, gradient-thumb feature cards with hover lift, numbered step circles, plus-rotates-45 FAQ, and a dark gradient CTA banner (`globals.css:13,16,19`). It is the page the design system was built for. Its ceiling is capped by the font failure and the pale, low-saturation light wash.

**Worst — History (2.5).** 62% bright + 37% dark in the first viewport, 64 DOM nodes, 359px of text, and an empty state with no illustration or CTA (`history/page.tsx:53-55`). The "dark block" the ground truth flagged is the global footer (`layout.tsx:9` + `globals.css:37`) — on a page with almost no content it reads as a bug. Explore (3.5) and Roadtrip (3.0) are close behind: functionally present, aesthetically absent.

**Honorable mention — Plan workspace (6.5):** if you weigh "does the page show the product doing its job," it wins on real photos + map + chat. It loses on the overflow bug and the 9-button toolbar.

---

## 1) Executive summary (250 words)

Across eight pages, "Mình Đi Đâu Thế" averages 4.6/10 on first-viewport beauty: a coherent, well-tokenized design system applied functionally, but with no page reaching its visual potential. The single most damaging defect is global: Inter/Fig Grotesk are declared and never loaded, so every display headline — the 88px landing hero, the 72px interior titles, the 52px plan titles — renders in Segoe UI, flattening the app's only true "brand moment." Second is the flagship plan page's horizontal overflow (`width:100vw` + negative full-bleed margins, globals.css:25), which leaves an 8px horizontal scrollbar and clips the map on every visit. Third, the global dark-plum footer dominates the first viewport of every short page: History is 37% dark, Roadtrip 31%, Login 25%, turning the app's *default* History state into "big title + one gray line + wall of black." The landing page is the visual best — a genuinely composed hero and the most crafted details — while History is the worst, with a text-only empty state and no anchor. Explore and Roadtrip are near-empty forms with no imagery; Roadtrip even asks vacationers to type latitude/longitude. The light theme is a low-saturation wash (mean_sat ≈0.03–0.05) while dark mode renders the lavender-on-black brand faithfully — evidence the product is dark-first and light mode is the afterthought. Fix fonts, fix the overflow, give the short pages real empty states, and the app's pages would jump roughly two points each.

## 2) Top 5 findings

1. **Fonts never load** — every page's display type falls back to Segoe UI (`globals.css:1`, ground-truth fact 1). **Blocker.**
2. **Plan workspace horizontal overflow** — `scrollWidth 1407 > 1399`, map clipped, horizontal scrollbar (`globals.css:25`). **Blocker.**
3. **Dark footer owns the first viewport of short pages** — History 37%, Roadtrip 31%, Login 25% dark (`layout.tsx:9`, `globals.css:37`); it is the footer, not an illustration. **High.**
4. **History empty state is text-only** — default anonymous state is "h1 + one line + dark slab" (`history/page.tsx:53-55`). **High.**
5. **Landing is the best page, History the worst** — Landing 7.0 (composed hero, most craft), History 2.5 (no anchor, footer crash); Explore 3.5 / Roadtrip 3.0 are form-only pages with no imagery. **Evidence-based ranking.**

## 3) Confidence: 7/10

The rendered pixel facts (bright/dark percentages, saturation, DOM/text counts, overflow geometry) are hard ground truth captured by CDP, and my code reading of `layout.tsx`, `globals.css`, and each page source is exact, so the dark-band (footer) and overflow (100vw) causes are **verified, not guessed** (confidence 9 on those two). The score numbers themselves are aesthetic judgment — inherently subjective — and I could not visually inspect the screenshots (no image input), so gradations like 3.5 vs 3.0 rest on pixel stats plus source, not on my eyes. Two data gaps lower confidence: the explore capture's missing footer band is unexplained (likely capture clipping), and the admin page has no rendered ground truth, so its 4.5 is code-only. Effective confidence: 7/10 — high on mechanism and relative ranking, moderate on absolute 0–10 values.
