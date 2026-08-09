# Layout Composition, Proportion & Whitespace — Audit Report

**Lane:** Layout composition, proportion, and whitespace beauty.
**Product:** Mình Đi Đâu Thế (Vietnamese AI travel planner, Next.js 15).
**Evidence:** Real rendered metrics from `00-ground-truth.md` (captured at 1440x1000, viewport ≈1399x873, Edge 151 CDP), plus static analysis of `frontend/app/globals.css`, `app/layout.tsx`, `app/page.tsx`, `components/Planner.tsx`, `components/PlanView.tsx`, `components/Navigation.tsx`, `components/Footer.tsx`, and the explore/roadtrip/history/settings pages.
**Scope note:** Colors, typography micro-detail, and component craftsmanship are covered by other agents. Where a whitespace problem is *caused* by a color decision (e.g., paper vs. white card contrast), I flag the layout consequence and hand off the cause.

---

## 1. Proportion & balance — the hero, and a 3095px page

### 1.1 The hero split (1.05fr / 0.95fr)

The hero is defined at `globals.css:13`:

```
.hero{display:grid;grid-template-columns:1.05fr .95fr;gap:56px;align-items:center;min-height:calc(100vh - 120px);padding:32px 0 64px}
```

At the rendered content width (~1152px inside `.shell` at `globals.css:1`, layout `app/layout.tsx:9`), the split is ≈592px / 536px with a 56px gutter. The 1.05/0.95 ratio is a nearly-symmetric split with a slight tilt toward the text column. For a landing hero, this is **legitimate and defensible**: a text+trust-bar left column and an interactive planner card on the right is a classic "product + app teaser" composition. The 56px column gap is generous (more than the 32px standard for tight 2-col splits) and gives the hero real air.

However, the honest verdict on *balance* is mixed:

- **The left column is 40–50% void.** The hero-left (`globals.css:13`) contains: an eyebrow pill, an h1 clamped up to 88px (`clamp(48px,6.5vw,88px)`), a 20px lead, and a two-element social-proof row (`app/page.tsx:29-43`). The h1 at 88px with `line-height:.98` is enormous; two lines of it occupy roughly 170px of the ~753px hero height. Below that sits one paragraph and a dot+stat row. The column is `justify-content:center` (`globals.css:13`), so the group is vertically centered — but the *group itself is short*. There is a large expanse of `--paper` above and below the text cluster.
- **The right column is dense.** The Planner card (`Planner.tsx:159-234`) is a full form: welcome bubble, three chips, chat input row, people input, a status block, and two disclaimers — wrapped in a 28px-padded card (`globals.css:19`) with a 6px gradient top bar (`globals.css:19`). Visually it anchors the fold.
- Net: the left column *reads* lighter than the right. This is acceptable (the eye lands on the card, the CTA), and the near-1:1 split keeps it from feeling lopsided. I would not call the hero composition broken — it is the best-designed region of the site. But the above-fold whitespace in the left column contributes directly to the "empty in light mode" perception measured in the ground truth (`00-ground-truth.md:47-48`: landing-light is 95.2% bright).

### 1.2 A 3095px landing page — good vertical use or sparse?

Ground truth records `scrollHeight=3095` (`00-ground-truth.md:25`). The page is: sticky nav (~60px + 32px margin, `globals.css:4`), hero (min-height calc(100vh−120px) ≈ 753px at a 873px viewport, `globals.css:13`), then **four** `.landing-section` blocks (`app/page.tsx:47-108`) each at `padding:72px 0` (`globals.css:16`), then footer.

Reconstructing the stack:
- Nav + margin ≈ 92px
- Hero ≈ 753px
- Featured section: 72 + (46px h2 + 40px section-head margin) + 260px card min + 72 ≈ 490px
- Steps section: 72 + 86 + ~26px-card-padding × 2 + content ≈ 430px
- FAQ section: 72 + 86 + 3 × ~60px items ≈ 410px
- CTA section: 72 + ~196px banner + 72 ≈ 340px
- Footer: 72px margin + ~380px content ≈ 452px

Total ≈ 2967px, consistent with the measured 3095px. **The page is long because the top-of-funnel marketing stack is honest: hero + social proof, feature cards, how-it-works, FAQ, CTA.** That is a normal landing structure. The problem is not length; it is **density uniformity**.

Every one of the four `.landing-section` blocks uses the *identical* `72px 0` padding, the *identical* 1px `--line` border-top, and the *identical* left-aligned `section-head` (`.section-head{max-width:var(--container-narrow);margin-bottom:40px}` at `globals.css:16`). There is no crescendo, no alternating background, no variation in horizontal rhythm. Section 2 (steps) and section 3 (FAQ) have nearly identical visual density — both are a left-anchored heading over a 3-across grid / 720px-narrow list. The result is that the vertical space is **evenly but monotonously allocated**; the page scrolls like a stack of equal cards rather than a designed narrative.

Compounding this, the *content inside* each section is thin:
- Featured cards have a 150px gradient thumbnail containing only a single emoji (`globals.css:16`, `app/page.tsx:54-60`). The emoji floats on a lavender gradient — decorative, but the card body is just a title + one line + a "→" affordance.
- Steps cards are a numbered pill + 19px title + one muted paragraph (`globals.css:16`).
- FAQ items are one-line summaries.

So each 72px-cushioned section wraps a small amount of content. **This is where "airy minimalism" tips toward "sparse": the whitespace is generous, but the design gives the eye no texture with which to appreciate it.** In dark mode the empty areas read as intentional atmosphere (dark paper, lavender accents); in light mode they read as an unfinished, low-fill page (`00-ground-truth.md:47-48`). Verdict: the hero is a good use of space; the four marketing sections are a *correct but uninspired* use of vertical space.

---

## 2. Whitespace quality — airy minimalism, or empty and unfinished?

The ground-truth pixel data is the most damning evidence in this entire audit:

- `landing-light.png`: **95.2% bright**, mean saturation 0.036, 94.6% #e0e0e0 (quantized paper).
- `explore-light.png`: **96% bright**, 95.7% near-white — "nearly empty white page."
- `settings-light.png`: 94.3% bright.
- `plan-light.png`: 90.4% bright (map area adds muted tones).

(`00-ground-truth.md:46-56`)

Read honestly, the layout produces light-theme screenshots that are **95%+ blank canvas**. Three independent causes, ranked by layout-relevance:

1. **The white-on-paper card distinction is nearly invisible (`globals.css:1`).** Page is `--paper:#f7f6f3`; cards are `--surface:#ffffff`. The delta is ∆L ≈ 0.008 in sRGB. Cards, sections, and the page are visually the *same plane* in light mode. A `.card` border of `--line:#eae8ea` (also near-white) plus a shadow of `rgba(42,24,46,.05)` (`globals.css:10`) is far too subtle to register. This is a color-lane root cause, but its *layout consequence* is that the generous whitespace has no positive shape to contrast with — the page becomes void. Every card boundary that a layout engineer carefully padded with 24px (`globals.css:10`) is invisible, so the negative space reads as empty, not as framing.

2. **Real content voids.** The explore page (`app/explore/page.tsx:59-67`) renders only: eyebrow + h1 + lead + 4 tabs + one `inventory-search` card. There is no default data, no empty state artwork, no secondary content — the ground truth measured `text=574` px and `dom=80` (`00-ground-truth.md:79`). That is a **structurally empty page**: a 1152px-wide canvas holding a single form card. This is not aesthetic minimalism; it is an unfinished layout. Same family: the landing's left hero column and the four thin marketing sections from §1.2.

3. **The nav/footer anchors don't help the light mode.** The sticky nav is `background:rgba(247,246,243,.86)` (`globals.css:4`) — nearly the same as the page — so it does not read as a distinct chrome bar; it floats. The footer is the *only* strong full-bleed anchor (`globals.css:37`, `--ink` background), and it is tucked at the very bottom.

So: is it "airy minimalism" or "empty"? **Both, depending on theme.** Dark mode (`globals.css:42`) converts the same voids into atmosphere — #141014 page, #1f1222 surfaces, lavender accents, and the ground truth confirms dark screenshots look populated (`00-ground-truth.md:57-60`). Light mode, which is what a Vietnamese consumer app will overwhelmingly ship, reads as unfinished. A genuinely airy layout would still show *cards, images, map tiles, and section density*; here the majority of the frame is untouched paper. **The whitespace quality is tuned to dark mode and broken in light mode.** This is a Blocker-level perception problem for a consumer landing page, even though it is caused partly by color.

---

## 3. The workspace 3-column grid (chat / itinerary / map)

Defined at `globals.css:25`:

```
.workspace{display:grid;grid-template-columns:minmax(240px,.6fr) minmax(360px,1.2fr) minmax(340px,1.05fr);gap:16px;min-height:680px}
```

### 3.1 Column proportion math

At the real rendered width — workspace-page ≈ 1367px of content (100vw minus 40px padding, `globals.css:25`) — the grid resolves to approximately:

- Chat: **323px** (240px min + ~83px share)
- Itinerary: **526px** (360px min + ~166px share)
- Map: **485px** (340px min + ~145px share)
- Plus 2 × 16px gutters = 32px. Sum ≈ 1366px.

Ratios ≈ **1 : 1.63 : 1.50** (chat : itinerary : map).

**Judgment: the priority ordering is right, but the map column is proportionally too close to the itinerary.** In a 3-pane travel workspace the *itinerary is the primary artifact* and the map is the *secondary viewer*. Here the map (485px) is 92% of the itinerary's width (526px) — they feel like two near-equal content panes squeezed around a thin chat rail. Compare design norms: a chat/inspect/map layout typically gives the primary content ~2× the secondary viewer. The `.6fr/1.2fr/1.05fr` ratio (`globals.css:25`) simply doesn't push the itinerary column enough. It also fails to *visually declare* which pane matters — a layout question, not a color one.

Two further balancing problems:

- **Height is fine, but for the wrong reason.** `.workspace{min-height:680px}` with `align-items` defaulting to stretch makes all three columns equal height, while the *internals* disagree: chat-panel `min-height:620px` (`globals.css:25`), map `.map{flex:1;min-height:520px}` + legend ≈ 570px, itinerary `max-height:720px` + internal scroll (`globals.css:25`). Equal column bottoms are good; the three panes scroll independently (chat `overflow:auto`, itinerary `overflow:auto`, map fixed), which is a defensible tool pattern but means the three "cards" never align their content baselines — only their boxes.
- **The gutter is 16px, not 20–24px.** Two 16px gutters between three large surfaces is the tight end of design norms (typical panel apps use 20–24px). At 1500px container this produces a slightly *cramped* feel between the itinerary and map, which are the two panes the eye most wants separated. 16px works for the tight chat rail; it is tight for the map boundary.

### 3.2 Card padding inconsistency within the workspace

`.workspace .card{border-radius:var(--radius-lg);padding:18px}` (`globals.css:25`) overrides the global `.card{padding:24px}` (`globals.css:10`). The panels therefore run at **18px** internal padding while every other card on the site runs at 24px. 18px is not on the 8px grid (24→16 would be), and it makes the three most important working surfaces feel denser than the rest of the product. For a *planning workspace* this densification is defensible; but the value 18 is arbitrary (see §4).

---

## 4. Vertical rhythm — consistent system or arbitrary values?

Collecting every spacing literal used in layout/whitespace roles:

| Value | Where |
|---|---|
| 8px | chip padding v (`globals.css:7`), trip-facts padding v (`globals.css:25`) |
| 10px | messages gap (`globals.css:22`), slot gap (`globals.css:25`), map-panel gap (`globals.css:25`) |
| 14px | nav padding v (`globals.css:4`), slot padding (`globals.css:25`), timeline gap (`globals.css:34`), day-tabs margin-b (`globals.css:25`) |
| 16px | nav gap, featured/steps gap (`globals.css:16`), workspace gap (`globals.css:25`), trip-header margin-b (`globals.css:25`) |
| 18px | workspace card padding (`globals.css:25`) |
| 24px | card padding (`globals.css:10`), shell padding (`globals.css:1`) |
| 26px | step padding (`globals.css:16`) |
| 28px | planner padding (`globals.css:19`) |
| 32px | hero top padding (`globals.css:13`), footer-grid gap (`globals.css:37`) |
| 40px | section-head margin-b (`globals.css:16`), login-card padding (`globals.css:34`) |
| 52px | landing-section mobile padding (`globals.css:16`) |
| 56px | hero column gap + hero top-to-h1 (`globals.css:13`), footer padding top (`globals.css:37`) |
| 64px | hero bottom padding (`globals.css:13`), login-card margin (`globals.css:34`) |
| 72px | landing-section padding (`globals.css:16`), site-footer margin-top (`globals.css:37`) |

**There are 14 distinct spacing values, of which 18, 26, and the 14/15 split (bubble padding `12px 15px` at `globals.css:22`) break the 8px modular grid.** The 8/16/24/32/40/56/64/72 run is a legitimate 8px scale, but:

- **No named scale.** The values are written inline per-rule rather than as `--space-*` tokens. This is why 18, 26, 14, 15, 11, 13, 38px (trip-action height, `globals.css:25`) all appear as orphans. A `:root` space scale (like the color tokens at `globals.css:1`) is entirely absent.
- **Three "large" values with no hierarchy: 56 / 64 / 72.** Hero uses top-32/bottom-64, sections use 72, footer uses margin-72/top-56. The eye cannot infer a rule from these; they look picked per-section.
- **The page-to-page density jump is stark.** Landing sections breathe at 72px; the plan page's workspace runs at 16/18/14px. That is a *deliberate* tool-vs-marketing split, and it is the right instinct — but the transition from a 1200px landing (24px shell padding) to a full-bleed 1500px workspace with 18px card padding and 20px edge padding (`globals.css:25`) is jarring, not graduated.

Verdict: **there is a loose 8px grid underneath, but it is not enforced, and the arbitrary orphans (18, 26, 15, 11) read as hand-tuned rather than system-designed.** A layout auditor would score this 5/10 for consistency.

---

## 5. The overflow defect — confirmed, and it is a real beauty failure

Ground truth is explicit (`00-ground-truth.md:15-20`):

- `<main class="workspace-page">` bounding: **L=−7, R=1407, W=1414** while viewport **vw=1399**.
- Leaflet map SVG + 4 tiles extend to **R=1434**.
- `scrollWidth=1407 > clientWidth=1399` → **horizontal scrollbar appears**.

Root cause (code-confirmed): `globals.css:25`:

```
.workspace-page{max-width:1500px;margin:0 auto;padding:0 20px;width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)}
```

Because `100vw` includes the scrollbar (~8px), it exceeds the viewport's client width (1399). The negative-margin centering math (`calc(50% - 50vw)`) then leaves the element 8px wider than the viewport. Worse, this rule is applied to an element **nested inside `.shell`** (`app/layout.tsx:9` wraps all children in `<div className="shell">`, `globals.css:1`). The full-bleed is achieved by breaking out of the shell via negative margins — a fragile technique that is sensitive to scrollbar width, and it is exactly what broke.

**Severity as a beauty defect: High-to-Blocker.** The consequences are visible, not cosmetic:

- A **horizontal scrollbar appears on the plan page** — the app's core product screen. On Windows (the measured platform) an overlay-less scrollbar permanently shrinks the layout and adds chrome.
- **The map tiles bleed to R=1434**, 34px past the main's right edge (1407) and 35px past the viewport (1399). The right pane's edge visually overflows the frame — a broken composition where the secondary pane is cut by the window edge.
- **Scrollbar appearance/disappearance jitter**: if the page is taller than the viewport (it is — `scroll=1407x1496`, `00-ground-truth.md:78`), the vertical scrollbar is always present; but at any viewport where the vertical bar appears or the window is resized, the 100vw-based width shifts, causing a horizontal layout jump.

This is a genuine **layout composition defect on the flagship screen**, triggered by a "recent full-bleed fix" (`00-ground-truth.md:20`). It must be reported as the single most concrete layout bug. The proper full-bleed approach (margin-less break-out from a max-width parent, or `width:100vw` with `scrollbar-gutter`/`overflow-x:clip` on the parent) is a code concern, but the *visible result* — overflow, clipped map, scrollbar — is squarely in this lane.

---

## 6. Alignment discipline across pages

### 6.1 Container widths are inconsistent (and it shows)

The global content rail is `.shell{max-width:1200px;padding:0 24px}` (`globals.css:1`, `app/layout.tsx:9`). Which pages respect it:

| Page | Container | Actual content width @1399 viewport |
|---|---|---|
| Landing (`app/page.tsx`) | `.shell` → 1200 | 1152px |
| Explore (`globals.css:28`, `app/explore/page.tsx:59`) | `.explore-page{max-width:1200px}` inside `.shell` | 1152px |
| Roadtrip (`app/roadtrip/page.tsx:56`) | inside `.shell` (no own container) | 1152px |
| History / Settings / Login | inside `.shell` (+ own narrow card widths) | 1152px |
| **Plan (`PlanView.tsx:120`, `globals.css:25`)** | **`.workspace-page{max-width:1500px}` full-bleed 100vw** | **~1367px edge-to-edge** |

So every page is a 1152px centered column with 24px gutters, and the **plan page suddenly jumps to edge-to-edge 1500px with 20px gutters**. Navigating from explore → a plan → roadtrip moves the left content edge from x≈123 to x=0 to x≈123. That is a **visually jarring frame change**: the title block and cards re-anchor, the whitespace margin collapses to the physical screen edge, and the plan page's content reaches farther than any other page. For an app whose flow is *landing → plan → iterate*, the frame discontinuity is noticeable.

There is also a **second alignment slip within the workspace itself**: `.workspace-page` is full-bleed, but the `.trip-header`, `.trip-facts`, `.workspace`, and `.disclaimer` inside it use no shared inner container — they just inherit the 20px padding. Meanwhile on the plan page the version/comments/feedback drawers are `max-width:760px` (`globals.css:25`) and left-aligned, while the trip-header spans the full 1500px. So the plan page internally mixes full-width and narrow-width content with no declared alignment rule.

### 6.2 Within-page alignment breaks

- **FAQ heading vs. FAQ list (confirmed misalignment).** `.section-head{max-width:720px;margin-bottom:40px}` is *left-aligned* (`globals.css:16`), but `.faq-list{max-width:720px;margin:auto}` is *centered* (`globals.css:16`). In the FAQ section (`app/page.tsx:82-96`) the h2 sits at the shell's left edge while the FAQ items begin ~216px in. A section's heading and its content should share a left edge; here they don't. This is a real alignment discipline failure.
- **The three "same-sized" h1s.** The global `main:not(.hero)>h1{font-size:clamp(38px,5vw,62px)}` (`globals.css:10`) is overridden by explore/roadtrip to `clamp(42px,5.5vw,72px)` (`globals.css:28`, `globals.css:31`) and by the plan page to `clamp(30px,3.6vw,52px)` (`globals.css:25`). The flagship plan page's title is *smaller* than explore's — the hierarchy inverts between pages.
- **History page has no container class** (`app/history/page.tsx:55` renders a bare `<main>`), so its h1 gets the 62px global max, but its `.timeline` cards stretch the full 1152px while the plan page's itinerary (the same `.timeline` class, `globals.css:34`) lives in a 526px pane. Same class name, two completely different scales of composition.

---

## 7. Negative space around cards, bubbles, chips, and slots

Micro-spacing is mostly *competent*; a few values deserve notes.

- **Chat bubbles: well-tuned.** `.messages{gap:10px}`, `.bubble{padding:12px 15px;max-width:92%}` (`globals.css:22`). The 92% max-width with asymmetric 6px tail radii (`border-bottom-left-radius:6px` / `border-bottom-right-radius:6px`, `globals.css:22`) is a classic chat composition. 10px vertical gap between bubbles is tight but appropriate for a dense assistant log. The `assistant-dot` ring (`box-shadow:0 0 0 6px var(--lavender-soft)`, `globals.css:22`) gives the rail its one good piece of "breathing" chrome. **Score: good.**
- **Chips: fine, slightly squat.** `.chip{padding:9px 16px}` (`globals.css:7`) vs `.quick-actions .chip{padding:8px 13px}` (`globals.css:7`) and planner chips at the same 8/13 — three different chip paddings across the app for the same component. Negligible per-chip, but it undermines the "same element, same footprint" discipline.
- **Itinerary slot grid: the one well-engineered rhythm.** `.itinerary-panel .slot{grid-template-columns:28px 56px 1fr auto;gap:10px;padding:14px;margin-bottom:10px}` (`globals.css:25`). The 28px stop-index circle, 56px time rail, flexible title column, and auto-width swap button, with the description paragraph deliberately spanning `grid-column:2/-1` (`globals.css:25`) to indent under the title — this is *thoughtful composition*. The `.selected` ring (`box-shadow:0 0 0 4px var(--lavender-soft)`, `globals.css:25`) is a clean focus affordance. **Score: good.**
- **But the timeline gap conflicts with the slot margin.** `.timeline{display:grid;gap:14px}` (`globals.css:34`) *and* `.slot{margin-bottom:10px}` (`globals.css:25`) both apply on the plan page — grid gap (14px) plus item margin (10px) yields an effective ~24px spacing between slot cards, while the history page's `.timeline` links get only the 14px gap. Same class, different spacing. **Layout inconsistency, confirmed.**
- **Workspace panel internals are crowded.** `panel-title{margin-bottom:14px}` (`globals.css:25`), day-tabs at 14px margin, trip-facts at `margin:18px 0` (`globals.css:25`), slot padding 14px. The three panes sit at 18px card padding with 16px gutters — everything *works*, but the workspace is uniformly denser than the marketing pages with no visual relief between the header, facts row, tabs, and content.

---

## 8. Section borders & separation rules

The separation system is: `border-top:1px solid var(--line)` on every `.landing-section` (`globals.css:16`), a nav border-bottom (`globals.css:4`), `border-top:1px solid rgba(255,255,255,.12)` inside the footer (`globals.css:37`), and hairline `--line` borders on most cards.

**Judgment: not too many rules — too weak and too uniform.** Four consecutive sections each opening with an identical 1px `--line` border reads as "stack of items" rather than "designed sections"; the border is nearly invisible in light mode (e.g., `#eae8ea` on `#f7f6f3`). The design relies on borders alone for section separation — there is no alternating surface, no inset/outset rhythm, no spacing differential — so the page *feels* flat. This is the same root disease as §2: separation rules exist on paper but carry no visual weight. The footer's `border-radius:var(--radius-xl) ... 0 0` (`globals.css:37`) is the one place a section boundary is allowed to be *physically* distinct (a rounded, dark cap), and it's the only one that reads.

One structural oddity: the sticky nav is `max-width:1200px;margin:0 auto 32px` (`globals.css:4`) — it does **not** span the viewport. Its `border-bottom` stops at the 1200px container edge, so on a 1399px screen there is a floating toolbar with a 32px paper moat below it and paper on both sides. The nav is the *only* page-level element (besides footer) that isn't full-bleed, and its 32px bottom margin means content passes beneath a nav that visibly floats rather than docks. As a composition decision this is defensible (a floating pill-less bar), but combined with the plan page being full-bleed and everything else being shell-bound, the "edge discipline" of the site is inconsistent.

---

## Categorized findings

### Blocker
1. **Light mode reads as an empty/unfinished page (`00-ground-truth.md:47-48`; `globals.css:1,10,16,28`).** 95–96% of the frame is near-white with no card-to-page distinction (white surface on paper, 1px near-white lines, 5%-alpha shadows). Landing hero left column and explore page are voids. The layout's whitespace is only "beautiful" in dark mode.

2. **Plan page horizontal overflow from the `width:100vw` full-bleed (`00-ground-truth.md:15-20`; `globals.css:25`).** scrollWidth 1407 > clientWidth 1399 → visible horizontal scrollbar; map tiles bleed to R=1434, clipped by the window edge. The app's flagship screen is broken at its right margin.

### High
3. **Explore page is structurally empty (`app/explore/page.tsx:59-67`; `00-ground-truth.md:49,79`).** One form card on a 1152px canvas, no default content, no empty state, dom=80/text=574. Unfinished, not minimal.

4. **Container inconsistency across pages (`globals.css:1` vs `globals.css:25`; `app/layout.tsx:9`).** 1200px/24px shell on landing, explore, roadtrip, history, settings; edge-to-edge 1500px/20px on plan. Frame and left-edge jump when navigating into the core screen.

5. **Workspace 3-column proportion under-weights the primary pane (`globals.css:25`).** Chat : itinerary : map ≈ 1 : 1.63 : 1.50 — the itinerary gets only ~1.1× the map, and the 16px gutters are tight for the map boundary (norm 20–24px). The 18px workspace card padding breaks the 24px card norm.

### Medium
6. **The vertical rhythm is a hand-tuned 8px grid with orphans (`globals.css` various: 18, 26, 15, 11, 38px), no space tokens, and an unexplained 56/64/72 triplet.** Works fine page-internal; inconsistent across pages (72px landing vs 16/18px workspace).

7. **FAQ heading/content misalignment (`globals.css:16`).** `.section-head` left-aligned vs `.faq-list` `margin:auto` centered — a ~216px internal edge break in the same section.

8. **Four identical `border-top` sections with no visual variation (`globals.css:16`).** Separation exists but is weightless in light mode; no alternating rhythm across the 3095px landing.

9. **Timeline double-spacing (`globals.css:25` + `globals.css:34`).** `.slot` margin-bottom 10px + `.timeline` gap 14px = ~24px on the plan page vs 14px on history; same class, different spacing.

### Low / Note
10. **Chip padding varies across contexts (9/16 vs 8/13; `globals.css:7`).** Same component, different footprint.
11. **Plan page h1 is smaller than explore/roadtrip h1 (`globals.css:25` vs `globals.css:28,31`)** — heading hierarchy inverts between pages.
12. **The hero left column is ~40% void** but the 1.05/0.95 split and 56px gutter keep it balanced — the strongest layout decision on the site; only flagged because of the light-mode whiteness.
13. **The sticky nav floats (1200px, 32px moat, border stops at container) while the footer is full-bleed and rounded (`globals.css:4,37`)** — edge discipline is inconsistent, though each choice is individually acceptable.

---

## Executive summary (250 words)

Mình Đi Đâu Thế's layout is a competent, conventional structure undermined by two failures: a light theme that renders as a near-empty canvas, and a flagship screen that overflows its viewport. The bones are good — the hero's near-1:1 text/planner split with a 56px gutter is the best composition on the site; the itinerary slot grid (28px index / 56px time / flexible title, description indented) is genuinely well-engineered; the workspace's chat/itinerary/map priority is the right instinct. But none of it survives contact with light mode: paper-white page, white cards, 1px white borders, and 5%-alpha shadows collapse every layout decision into one indistinguishable plane, and the measured screenshots are 95–96% blank. The explore page is a single form card floating on a 1152px void. The four 72px landing sections stack monotonously behind identical hairlines, so the 3095px page scrolls like equal cards rather than a designed narrative. The plan page — the app's core — carries a real horizontal-overflow defect (scrollbar appears, map tiles clip at the window edge) caused by a `100vw` full-bleed hack applied inside a 1200px shell. Containers jump from 1200px/24px to edge-to-edge 1500px/20px between pages; spacing values are a hand-tuned 8px grid with orphans (18, 26, 15px). This layout is *structured and workmanlike, not designed with intent*: the primitives are right, the system and the light-mode rendering are not.

## Top 5 findings

1. **Blocker — Horizontal overflow on the plan page** (`globals.css:25`; `00-ground-truth.md:15-20`): `width:100vw` + negative-margin full-bleed inside the 1200px shell → scrollbar + map tiles clipped at R=1434. The core screen breaks its own frame.
2. **Blocker — Light mode is 95%+ blank** (`globals.css:1,10`; `00-ground-truth.md:46-56`): white cards on paper, hairline borders, 5%-alpha shadows → whitespace reads as emptiness, not minimalism. Only dark mode makes the layout legible.
3. **High — Explore page is structurally empty** (`app/explore/page.tsx:59-67`): one search card on 1152px, dom=80/text=574, no default state. Unfinished page, not minimal design.
4. **High — Container system is inconsistent** (`globals.css:1` vs `:25`): 1200px/24px on six pages, edge-to-edge 1500px/20px on the plan page; the frame jumps when entering the core screen.
5. **High — Workspace proportions under-weight the itinerary** (`globals.css:25`): 1:1.63:1.50 chat/itinerary/map with 16px gutters and 18px card padding — the primary pane is barely wider than the secondary viewer.

## Confidence

**8/10.** The overflow, whitespace, emptiness, and proportion facts are directly measured in ground truth (scrollWidth 1407 vs 1399; 95–96% bright pixels; text=574 on explore) and confirmed in CSS, so the empirical claims are solid. The deduction of −1 comes from two honest caveats: (1) the computed-style/light-mode ambiguity noted in `00-ground-truth.md:67-73` means the *perceived* light theme could differ slightly from the pixel captures, though the code-level white-on-paper card contrast is unambiguous; and (2) the "designed vs. stacked" verdict, the 16px-gutter norm, and the workspace column-proportion judgment are aesthetic calibrations where a competent reviewer could reasonably differ by one severity step. Layout facts: high confidence. Taste judgments: medium. Net: 8/10, not rounded up.
