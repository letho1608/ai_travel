# 02 — Typography, Type Scale & Visual Rhythm (Beauty Audit)

**Agent lane:** Typography / type scale / visual rhythm.
**Scope:** text styling beauty only (letterforms, sizes, line-heights, tracking, weights, vertical rhythm of type). Layout grid and color are other lanes' territory; I touch them only where a value is typographically motivated.
**Method:** source inspection of `frontend/app/globals.css`, `frontend/app/layout.tsx`, `frontend/package.json`, all `page.tsx` files and `components/`; cross-checked against rendered ground-truth JSON captured from headless Edge 151 (`visual_landing.json`, `visual_light_landing.json`, `visual_plan.json`, `visual_light_plan.json`, `visual_light_explore.json`, `visual_light_roadtrip.json`, `visual_light_login.json`) and `00-ground-truth.md`. All rendered numbers cited below are measured, not guessed.

---

## 1. The font-loading defect — the intended typography never renders (BLOCKER)

### 1.1 The evidence chain

The design token declares Inter first in the stack:

- `frontend/app/globals.css:1` — `--font:"Inter","Fig Grotesk",system-ui,sans-serif` and `body{...font-family:var(--font);...}`.

But nothing ever loads Inter or Fig Grotesk:

- `frontend/app/layout.tsx:1-9` — `RootLayout` imports exactly two stylesheets: `"./globals.css"` and `"leaflet/dist/leaflet.css"`. There is no `next/font` call, no `<link>` to Google Fonts, no `@font-face`, no `<style>`.
- `frontend/package.json:12-18` — dependencies are `next`, `react`, `react-dom`, `@types/leaflet`, `leaflet`. No `@fontsource/*`, no `next/font` usage possible via a font package, nothing.
- A recursive search of `frontend/app` and `frontend/components` for `Inter|next/font|@font-face|preconnect|fontFamily` returns exactly two hits: the `--font` token itself in `globals.css:1`, and the Google **Sign-In** script `https://accounts.google.com/gsi/client` in `frontend/app/login/page.tsx:65` (that is an OAuth script, not a font, and it is conditional). There are zero font files in the repo (no `.woff/.woff2/.ttf/.otf` anywhere under `frontend/`).
- Ground truth confirms the runtime consequence: `00-ground-truth.md:11-13` — `document.fonts` shows **zero Inter faces loaded**; `visual_landing.json:353-356` — the only `fontsUsed` are `"Times New Roman"` (which the audit confirmed lives on hidden `<head>/<script>` nodes, never on visible UI) and the declared stack string `Inter, "Fig Grotesk", system-ui, sans-serif`. No `@font-face` ever registers, so `Inter` and `Fig Grotesk` are dead names in a fallback chain that terminates at `system-ui` → **Segoe UI** on Windows.

### 1.2 What this does to the beauty

This is not a "minor fallback." The whole type system was tuned against a ghost. Inter is a tall-x-height, neutral grotesque with tight default side-bearings and generous aperture; Segoe UI is a humanist UI face with a **shorter x-height, wider letterforms and different stroke modulation**. Concretely, at render time:

- **Body text:** Segoe UI at 13–16px reads visibly looser and "system" — the same font every default Windows app uses. The crafted "paper + lavender" identity (see color lane) is carried by text that screams *unstyled Windows page*, so the brand's typographic voice is absent.
- **Display sizes:** The hero's `letter-spacing:-.035em` and the section `-.03em` (globals.css:13,16) were tuned for Inter's metrics. Segoe UI's wider advance widths crowd those negative trackings; at 88px that is ~-3.08px, and the Vietnamese stack (`Đ`, `ộ`, `ế`, `ể`, `ơ`, `ư`) carries more ink per glyph in Segoe UI. The headline reads denser than intended.
- **Weight fidelity:** Segoe UI ships 300/350/400/600/700 — **no 800, no 900**. Every `font-weight:800` heading and `900` brand/button (globals.css:1,4,10) is rendered via the engine's **synthetic emboldening** (fake bold). At 88px hero and 62px titles, fake-bold Segoe UI is coarse where Inter's designed 800 is crisp; the "premium" headline gesture is undercut by a bloated letterform.
- **Vietnamese diacritics vs line-height:** `h1,h2,h3{line-height:1.08}` and `.hero h1{line-height:.98}` (globals.css:1,13). At 88px, lh 0.98 gives an 86.24px line box (measured, `visual_landing.json:167-169`) for glyphs whose accents (ấ/ệ/ộ) can exceed cap+ascender extent in Segoe UI. Inter fits tight leading; Segoe UI's diacritic metrics make 0.98 clipping-prone. Same risk at 46px/1.08 (`49.68px`, `visual_landing.json:156`).

### 1.3 Severity for beauty

**Blocker.** Every statement below about "the design" is conditional on a font that never arrives. The *layout* survives, but the typographic identity — the layer that carries most of the "beauty" a user perceives on first scroll — is generic OS chrome. Fixing this is a one-file change (e.g., `next/font/google` Inter with `variable` display, or a self-hosted `@font-face`), which makes it high-leverage. Note the app does set `-webkit-font-smoothing:antialiased` (globals.css:1) — the author *cared* about rendering quality, which makes the missing font load more of an oversight than indifference.

---

## 2. Type scale — a half-remembered modular scale with holes and duplicates (HIGH)

### 2.1 Rendered scales

Landing (light, `00-ground-truth.md:22-24`, `visual_light_landing.json`):

```
13px×13   14px×23   15px×4   16px×58   17px×1   18px×1   19px×4   20px×5
44px×4    46px×3    88px×1
```

Plan (`00-ground-truth.md:27`, `visual_light_plan.json`): `10, 11, 12, 13, 13.33, 14, 15, 16, 18, 18.72, 19, 20, 22, 50.9` — **14 distinct sizes**, no two-step rhythm.

### 2.2 The 13→20 run is linear noise, not modular rhythm

Compute the ratios for the body/micro band:

```
13→14 = 1.077   14→15 = 1.071   15→16 = 1.067   16→17 = 1.062
17→18 = 1.059   18→19 = 1.056   19→20 = 1.053
```

These are **+1px linear steps** — a "bag of eyeballed sizes," not a modular scale. A modular scale (say 1.25) from 13 would give 13 / 16.25 / 20.3 / 25.4 / 31.7 / 39.7 / 49.6 / 62 — note how 13→16→20 is almost exactly `×1.25` twice. **The small end of this scale was originally derived from a 1.25 major-third**, and then the author kept inserting 14, 15, 17, 18, 19 as one-off fixes until every integer 13–20 is in use. Eight distinct sizes inside an 8px range, most of them doing the same "secondary text" job:

- **13px** chips, trip-facts, day-tabs, stop-index, slot body copy, footers (globals.css:10,25,31,37)
- **14px** nav links, bubbles, card copy, footer links (globals.css:4,16,22,37)
- **15px** buttons (globals.css:7)
- **16px** body/inputs (UA default, see 2.3)
- **17px** section-head + CTA paragraphs (globals.css:16)
- **18px** chat send button (globals.css:22)
- **19px** lead, step h3, brand (globals.css:4,10,16)
- **20px** hero lead, featured h3, footer brand (globals.css:13,16,37)

The practical tell: a user scrolling the landing sees body-sized text at 13, 14, 15, 16, 17, 19 and 20px *in the same viewport* (footer 13–14, bubbles 14, cards 14, leads 19–20). Nothing reads as "wrong," but nothing reads as *designed* either — it is the profile of a stylesheet grown by accretion.

**Is 16px the body?** Only by accident. `body{...}` in globals.css:1 sets **no `font-size`**, so body copy, `<p>`, and un-styled text all render at the **UA default 16px** (this is why 16px is the most common size, 58× on landing). There is no `--text-base` token; 16px is an implication, not a decision. Body copy at 16px/1.55 is a defensible default, but the entire small-end band (13–20) is hardcoded per-component with no shared tokens anywhere in `:root`.

### 2.3 The 20→44 gap and the 44/46 collision

Between the largest *card/lead* size (20px) and the first *section heading* size there is a **×2.2 jump with nothing in between** (no 24, 28, 32, 38). For a "display jump" this direction is fine, but the landing's heading band is then fractured:

- `.section-head h2{font-size:clamp(30px,4vw,46px)}` — globals.css:16 → renders **46px** (`visual_landing.json:273-275` "Đi đâu tiếp theo", 46px ×3).
- `.cta-banner h2{font-size:clamp(30px,4vw,44px)}` — globals.css:16 → renders **44px** (`visual_landing.json:317-319` "Sẵn sàng lên kế hoạch chưa?").

Two h2 treatments differ by 2px (ratio 1.045) — a **near-duplicate that reads as a clash**: the final CTA heading is *smaller* than the section headings above it, so the page's last big statement decrescendos instead of crescendoing. Worse, the "44px×4" count includes **three featured-card thumbs whose emoji icons are 44px** (`featured-card .thumb{font-size:44px}`, globals.css:16). Emoji glyphs — the biggest color objects in the featured section — are exactly the same pixel size as the CTA headline. That is a type-scale accident: the emoji thumbs should be display-graphic scale, not heading scale.

### 2.4 Is the 88px hero justified or overscaled?

`clamp(48px,6.5vw,88px)` (globals.css:13), renders 88px, lh .98, ls -3.08px (measured `visual_landing.json:162-173`). The copy is two short Vietnamese lines ("Đi đâu / để mình lo."), so it survives the size. Judgment: **directionally justified, magnitude slightly overscaled.** 88/46 = 1.91× over the section h2 — a hero should lead its section heads by ~1.4–1.6×, and 88 is also 4.4× body (16). Combined with fake-bold Segoe UI (1.2), 88px is near the edge of "big and confident" tipping into "bloated." It is not the worst offender — the 44/46 collision is — but I would rate it **Low-to-Medium**: the size is defensible; the rendering font is what makes it feel heavy. On mobile it collapses to 34–48px (globals.css:13) which is fine.

### 2.5 UA-default leaks pollute the plan scale

The plan page's 14-size "scale" is dirtied by **browser defaults and third-party text the design never set**:

- `18.72px ×7` — itinerary **h3** place names (`visual_plan.json:341-374`). `h1,h2,h3{}` (globals.css:1) sets weight/lh/tracking but **no font-size**, so un-styled h3s render the **UA default 1.17em = 18.72px**. The design never chose a size for the most important text in the itinerary panel.
- `13.3333px ×7` — the slot **`<small>`** cost/note text (UA `small` ≈ 0.83em). Never styled.
- `22px ×4`, weight 700 — **Leaflet map-control text** (node_modules Leaflet CSS declares `font-size:22px`); third-party noise in the type scale.
- `10px ×3` — Leaflet attribution, deliberately shrunk via `.map-panel .leaflet-control-attribution{font-size:10px}` (globals.css:40) — a 10px sub-label under an 800-weight UI is the only "caption" step and it belongs to a map library, not the design system.
- `50.904px` — the plan title `clamp(30px,3.6vw,52px)` (globals.css:25) — the *only* intentional display size on the page, floating alone with nothing between 22 and 51.

So the plan page's typography is: a designed 51px title + a designed 16px panel system + UA h3/small defaults + Leaflet chrome. That is the opposite of a modular rhythm.

### 2.6 Every page declares a different h1 — but only two ever render

The CSS *declares* seven different page-title sizes:

| Rule | Declared | Actual render |
|---|---|---|
| `.hero h1` (globals.css:13) | clamp(48,6.5vw,88) | **88px** |
| `main:not(.hero)>h1` (globals.css:10) | clamp(38,5vw,62) | **62px** (history/terms/privacy/support…) |
| `.trip-header h1` (globals.css:25) | clamp(30,3.6vw,52) | **50.9px** (plan) |
| `.explore-page>h1` (globals.css:28) | clamp(42,5.5vw,72) | **62px** |
| `.roadtrip-page>h1` (globals.css:31) | clamp(42,5.5vw,72) | **62px** |
| `.login-card h1` (globals.css:34) | clamp(36,5vw,52) | **62px** |
| `.settings-page h1` (globals.css:34) | clamp(34,4.5vw,54) | **62px** |
| `.admin-page>h1` (globals.css:40) | clamp(40,5vw,66) | **62px** |

Five of those per-page clamps are **dead code**, defeated by a specificity bug. `main:not(.hero)>h1` has specificity (0,1,2) — `main` type + `:not(.hero)` class + `h1` type — which beats `.explore-page>h1`, `.login-card h1`, `.settings-page h1`, `.admin-page>h1` (all 0,1,1). Ground truth proves it: explore, roadtrip and login all render **62px** h1 (`visual_light_explore.json:36`, `visual_light_roadtrip.json:36`, `visual_light_login.json:32`), not their declared 72/72/52. The plan title escapes only because its h1 sits inside `<header class="trip-header">`, not as a direct child of `<main>` (PlanView.tsx:121).

Honest read: the *intent* is seven inconsistent sizes (already bad); the *reality* is three (88 hero / 62 everything / 50.9 plan). The collapse gives cross-page consistency, but it is accidental, and it means a 62px title now sits on top of a 600px-wide login card (globals.css:34) — oversized for a form context, and the letter-spacing is the base `-.02em` rather than the `-.035em` the explore/roadtrip rules intended.

---

## 3. Line-height rhythm — six prose values and a form-control reset (HIGH)

### 3.1 The declared and rendered values

Prose line-heights declared across the stylesheet:

- `body` **1.55** (globals.css:1)
- `.lead` **1.65** (globals.css:10; hero lead 20px globals.css:13)
- `.bubble` **1.5** (globals.css:22)
- `.step p` **1.6** (globals.css:16)
- `.faq-body` **1.65** (globals.css:16)
- `slot p` **1.45** (globals.css:25)
- `.legal-page p` **1.7** (globals.css:40)
- `.map-popup` **1.4** (globals.css:25)
- headings **1.08** (globals.css:1), hero **0.98** (globals.css:13)

Five near-adjacent prose values (1.5, 1.55, 1.6, 1.65, 1.7) plus a 1.45 outlier — the same "near-adjacent bag" disease as the font sizes. A reader moves from a section-head paragraph (1.6) into an FAQ answer (1.65) into a disclaimer (1.5) into footer text (1.55) — the vertical cadence of text changes *within the same page* for no visual reason. Prose should be one value (~1.65 for Vietnamese); 1.45 at 13px (`slot p`) is the tightest prose on the site and the most accent-dense text (Vietnamese descriptions), i.e., exactly where you need *more* leading, not less.

Rendered confirmation from `visual_landing.json`: 14px text shows lh 21.7 (1.55), 21 (1.5 bubble), 22.4 (1.6 step) — three different line-heights on the same 14px size. 16px shows **24.8px (1.55) but also literally `"normal"`**.

### 3.2 The `normal` line-height on every form control (real bug, verified)

`visual_landing.json:64-71`: at 16px, rendered line-heights are `"normal"` and `"24.8px"`. The culprit is globals.css:1:

```css
button,input,select,textarea{font:inherit}
```

The `font` **shorthand** resets `line-height` to `normal` on every form control, discarding the body's 1.55. So on the landing planner, the chat input, the people input, the submit button and all chips render their text at UA `normal` (~1.2 for Segoe UI) while the labels and bubbles around them are 1.5–1.55. Same-size text at different leading is a classic "unpolished" tell — and this one is 100% mechanical. Fix is `font-family:inherit;font-size:inherit;` (and explicit `line-height:inherit`) instead of the shorthand. This affects **every input/button/select on the site** (planner, explore form, roadtrip builder, settings, login, admin).

### 3.3 Vietnamese diacritics at tight display leading

At `lh 1.08` (headings) and `0.98` (hero) with 88/62/46px text, the ascender+diacritic stack (`ế`, `ệ`, `ộ`, `ể` — e/ô/ơ with circumflex *and* tone) must fit the line box. These values were tuned for Inter (which packs Vietnamese accents tightly). In Segoe UI the risk of accent collision across lines is real at 0.98. Even in Inter, 0.98 on a two-line Vietnamese headline is "designed tight"; in the wrong font it is a clipping hazard. Flag as a coupling between the (missing) font and the aggressive leading.

---

## 4. Letter-spacing — direction is tasteful, values are inconsistent (MEDIUM)

### 4.1 The eyebrow family has four tracking dialects

The "micro-label / eyebrow" role is styled four different ways:

- `.eyebrow` — 12px, **uppercase**, `letter-spacing:.1em` (globals.css:10). Used on plan workspace (`Không gian chuyển đi`, PlanView.tsx:121), explore (`inventoryEyebrow`, explore/page.tsx:59), roadtrip, history, settings, support.
- `.hero .eyebrow` — 13px pill, **NOT uppercase**, `letter-spacing:.04em` (globals.css:13). Rendered ls 0.52px (confirmed `visual_landing.json:20-23`).
- `.footer-col h4` — 13px, uppercase, `.08em` (globals.css:37). Rendered 1.04px (confirmed).
- admin strip/metric spans — 12px, uppercase, `.07em` (globals.css:40).

One role, four tracking values (0.04/0.07/0.08/0.1em) and inconsistent case. The hero badge is a deliberate, defensible variant (badge vs. eyebrow), but the same class name means two treatments; and the uppercase `.1em` eyebrow turns a Vietnamese phrase into a widely-tracked ALL-CAPS string — at 12px with 0.1em the letters get airy and hard to read quickly. Pick one tracking for "eyebrow," reserve a tighter one for the badge.

### 4.2 Heading tracking: consistent direction, drifting values

Base `h1,h2,h3{letter-spacing:-.02em}` (globals.css:1); overrides `-.03em` (section-head h2, trip-header h1), `-.035em` (hero h1, explore/roadtrip h1). The *direction* is correct typographic practice (tighter tracking at larger display sizes), and the rendered values (-0.38px at 19px, -1.38px at 46px, -3.08px at 88px — all confirmed in `visual_landing.json`) are tasteful. The complaint is that the values aren't derived from a rule — `-.02` and `-.03` and `-.035` are three hand-picked numbers for the same job. This is the *least* problematic area; I'd call heading tracking the most competent typographic decision in the stylesheet.

---

## 5. Weight contrast — a strong ladder, mushy in the middle, synthetic at the top (MEDIUM)

### 5.1 The ladder as declared and as rendered

Declared: body **400**; nav links/chips **600**; labels/tabs **700** (globals.css:4,25,28); buttons/headings **800**; brand/panel-titles/stat **900** (globals.css:4,25,10); one **500** (`trip-facts .last-updated`, globals.css:25). Rendered weights on the landing run 400→900 with 500/600/700/800 all present (`visual_landing.json` weights arrays). That's a healthy 5-step ladder — the hierarchy is *strong*, not mushy, *except* at two points:

- **The 19/20px boundary is mushy.** Card titles h3 are 19px (step, globals.css:16) and 20px (featured, globals.css:16); the lead body is 19px (default) / 20px (hero). A 20px **body paragraph** (`.hero .lead`, globals.css:13) is the same size as a 20px **card title** (`.featured-card h3`). Only the 800-vs-400 weight separates them; at a glance, lead and heading compete. A card title should out-size body copy by at least one step.
- **800/900 are synthetic in Segoe UI** (no native faces exist, see §1.2). So the "strong" top of the ladder is fake-bold, which erodes the contrast gain — 400 Segoe UI vs synthesized-900 Segoe UI is a rougher, heavier jump than Inter's designed 400→800.

Within the nav bar the brand (900) sits against links (600) against the CTA pill (800 on brand background) — three weights in one 48px strip. It holds, but 900 for a 19px wordmark is overkill when 800 exists; "Mình Đi Đâu Thế" at 900 reads heavy in Segoe UI.

---

## 6. Component-by-component typographic check

### 6.1 Landing hero (`app/page.tsx:28-45`)
Eyebrow badge (13/.04em/800) → 88px h1 (0.98, -0.035em) → 20px lead (1.65) → 14px social proof. Structurally a classic and correct stack. Issues: the h1's `margin:18px 0` (globals.css:13) puts 18px between badge and headline and 18px below — an odd, non-grid number in an otherwise 12/20/40/72 rhythm; and everything is Segoe UI (1.2) and fake-bold.

### 6.2 Featured cards (`app/page.tsx:52-62`, globals.css:16)
44px **emoji** thumb (type-scale collision, §2.3) → 20px h3 (800) → 14px p (1.55) → 14px 800 "→" CTA. The `→ {t("createPlan")}` at 14px/800 is a nice micro-interaction flourish. Fine, but the h3 title is only 6px above its body copy — hierarchy relies on weight alone.

### 6.3 Steps (`app/page.tsx:71-78`, globals.css:16)
`::before` numeral badge 14px/900 in a 40px tile → 19px h3 → 14px p at **1.6**. The 19px step h3 vs 20px featured h3: two card-title sizes differing by 1px for the same role.

### 6.4 FAQ & CTA (`app/page.tsx:82-108`, globals.css:16)
FAQ summary 16px/800 (good, better than a default summary), answer 15px/1.65. The CTA h2 at 44px is *smaller* than the 46px section h2s (§2.3) — the layout's last headline shrinks. CTA lead inherits `.lead` (19px/1.65) but `.cta-banner p` forces 17px (globals.css:16) — the "lead" role renders at 17, 19 and 20px on the same page (hero lead 20, FAQ-adjacent 19, CTA 17).

### 6.5 Planner (`components/Planner.tsx:158-234`)
Welcome bubble 14px/1.5; quick chips 13px/600; chat input + people input 16px with **`line-height:normal`** (the `font:inherit` bug, §3.2); send button 18px "↑" glyph; two disclaimers 13px/1.5 stacked (Planner.tsx:232-233). The 18px ↑ next to a 16px input is a 2px jump that's harmless, but the input/button text sitting at `normal` while everything around it is 1.5–1.55 is the most visible inconsistency on the fold.

### 6.6 Plan workspace (`components/PlanView.tsx:120-131`)
- `workspaceEyebrow` uppercase 12/.1em — a long Vietnamese phrase in wide-tracked caps.
- h1 50.9px (-.03em) over 16px summary — good pairing.
- trip-facts 13px/600 pills; `last-updated` 13px/500 dashed — two weights for the same pill row.
- `.panel-title` 16px/**900** ×3 (chat, itinerary, map) — solid, if heavy.
- day-tabs 13px/700; itinerary slot h3 at **UA 18.72px** (§2.5), slot body p 13px at **1.45** (tightest prose on the site, Vietnamese text), time `<strong>` 14px, source link 11px, `<small>` at UA 13.33px. Four-plus sizes inside one itinerary row (18.72/14/13/13.33/11) = noisy density.
- map-legend 12px; Leaflet attribution 10px.

### 6.7 Explore (`app/explore/page.tsx:59,66`)
h1 (declared 72, renders 62, §2.6) → lead 19 → tabs 700 → form labels 13/700 → **the offer card misuses `.eyebrow` for hotel/airline names** (explore/page.tsx:66): a hotel name or airline list rendered at 12px uppercase with 0.1em tracking — long proper nouns in wide-tracked ALL-CAPS is a readability regression and semantically wrong (it's a title, not an eyebrow). Offer price is an h2 at 26px (globals.css:28) — fine — but it sits *below* the uppercase 12px "title," so the price visually outranks the offer name.

### 6.8 Roadtrip (`app/roadtrip/page.tsx:56`)
Same 62px h1; stop-row index in a 30px circle at 13px/800; form labels/inputs (16px `normal`); roadtrip-summary/multicity articles show `<span>` muted at 13px (globals.css:31). No serious offenders; it inherits the systemic issues.

### 6.9 Login / Settings / Footer
Login + settings h1 both render **62px** (specificity bug) — a 62px headline above a 600px card is oversized for a conversion page; the declared 52/54 (globals.css:34) were already large. Settings labels jump to **800** (globals.css:34) while explore labels are 700 and feedback labels 700 (globals.css:25) — three label weights for the same job. Footer is the most coherent block: 20/900 brand, 13/.08em uppercase columns, 14px links, 13px bottom bar (globals.css:37) — genuinely good micro-hierarchy, and the footer is where the "no font loaded" hurts least because its uppercase/label-heavy design survives system fonts.

---

## 7. Vertical rhythm — padding-based, ad hoc, no grid (MEDIUM)

### 7.1 The numbers

Heading margins: base `h1,h2,h3{margin:0 0 12px}` (globals.css:1); hero `18px 0` (globals.css:13); trip-header `8px 0` (globals.css:25); step h3 `0 0 8px`; footer h4 `0 0 16px` (globals.css:37); section-head `margin-bottom:40px` (globals.css:16); `.landing-section{padding:72px 0}` → 52px mobile (globals.css:16); site-footer `margin-top:72px` (globals.css:37); disclaimer `10px 0 0`; facts `18px 0`.

So the landing's heading-to-content cadence is 8 / 10 / 12 / 16 / 18 / 20 / 40 / 72 — an eight-value bag with **18px on both sides of the hero headline** (a non-multiple of the 8/4 grid the radii use, and inconsistent with the 12px default). Rendered gap distribution confirms there is essentially *no gap-based rhythm*: `00-ground-truth.md:29-30` — landing gaps are `{32px×1, 72px×1}` and plan `{32px×1}`; nearly all spacing is carried by padding, which the audit captured only sparsely. The plan page's internal rhythm (slot margin 10, panel-title margin 14, day-tabs margin 14, chat-box margin 14, bubbles gap 10, facts margin 18) is a cluster of near-misses (10/14/18) rather than a stepped scale.

### 7.2 Judgment

A 72px section rhythm with 40px section-head margins is a *workable* landing cadence — the spacing is generous and airy, and the empty-state-heavy light theme (95% bright pixels, `00-ground-truth.md:47-48`) leans on that air. The problem is inconsistency at the small end: 8 vs 12 vs 18 vs 20 for "gap after a heading" makes the same hierarchy feel tighter or looser in different sections. There is no typographic baseline grid, and no `--space-*` tokens (the `:root` token block has colors, shadows and radii but **zero spacing or type tokens**, globals.css:1).

---

## 8. Findings register

| # | Finding | Severity | Evidence |
|---|---|---|---|
| F1 | Inter/Fig Grotesk never load; entire UI renders in Segoe UI; 800/900 synthetic; tracking tuned for the wrong font | **Blocker** | layout.tsx:1-9; package.json:12-18; globals.css:1; 00-ground-truth.md:11-13 |
| F2 | No font-size on body, h1-h3, small, strong → body=UA 16px, h3=18.72px, small=13.33px leak into real UI | **High** | globals.css:1; visual_plan.json:341-374, 356-360 |
| F3 | Type scale is a bag of arbitrary sizes: 13–20 in 1px steps; 20→44 gap; 44/46 near-duplicate h2; emoji thumbs at 44px; 14 sizes on plan page | **High** | globals.css:13,16; 00-ground-truth.md:22-27 |
| F4 | `font:inherit` resets line-height to `normal` on every form control (16px text shows "normal" vs 24.8px) | **High** | globals.css:1; visual_landing.json:64-71 |
| F5 | Five prose line-heights (1.5/1.55/1.6/1.65/1.7) + 1.45 outlier on accent-dense Vietnamese text | **Medium** | globals.css:10,16,22,25,37,40 |
| F6 | `main:not(.hero)>h1` (0,1,2) kills five declared page-title sizes; everything but hero/plan renders 62px (on a 600px login card) | **Medium** | globals.css:10,28,31,34,40; visual_light_explore.json:36 |
| F7 | Eyebrow role has 4 tracking dialects (.04/.07/.08/.1em) and inconsistent case; offer cards misuse `.eyebrow` for hotel names | **Medium** | globals.css:10,13,37,40; explore/page.tsx:66 |
| F8 | No type/space tokens in `:root`; vertical rhythm is an ad hoc 8/10/12/16/18/20/40/72 with 18px hero margins, near-zero gap rhythm | **Medium** | globals.css:1,13,16; 00-ground-truth.md:29-30 |
| F9 | 88px hero is justified directionally but overscaled (1.91× h2, 4.4× body) and heavy in fake-bold Segoe UI | **Low–Med** | globals.css:13; visual_landing.json:162-173 |
| F10 | Card title/lead boundary mushy: 20px lead == 20px card h3; step h3 19px vs featured h3 20px; lead role at 17/19/20px on one page | **Medium** | globals.css:13,16 |
| F11 | Heading tracking direction is correct and tasteful (drifting values only) | **Note** | globals.css:1,13,16 |
| F12 | Footer is the most coherent typographic block | **Note** | globals.css:37 |

---

## 9. Executive summary (~250 words)

The typography of "Mình Đi Đâu Thế" is, bluntly, the weakest layer of its visual identity — and the dominant reason is one that has nothing to do with the CSS values: **the fonts the design was built around never load.** `layout.tsx` imports only `globals.css` and Leaflet, `package.json` contains no font package, and there is no `@font-face` or `next/font` anywhere, so every page renders in Windows' Segoe UI — with Inter's tight tracking, Vietnamese-tuned leading and crisp 800/900 weights replaced by Segoe UI's looser metrics, heavier glyphs, and *synthetic* fake-bold. The intended design, whatever its merits, is invisible. What actually renders is a type system that is otherwise a "bag of arbitrary sizes": eight font sizes between 13 and 20px in 1px steps (body text is an unstyled UA default 16px), a 20→44px hole, a 44/46px near-duplicate where the CTA heading is *smaller* than the section headings above it, emoji thumbs sized at 44px like a headline, and a plan page whose "scale" is polluted by browser-default h3 (18.72px) and `<small>` (13.33px) text plus Leaflet chrome. Line-height repeats the pattern — five prose values from 1.5 to 1.7, an accent-dense 13px paragraph at 1.45, and a `font:inherit` bug that resets every input and button to `normal`. To its credit: heading tracking direction is tasteful, the weight ladder is strong, and the footer is genuinely well-typed. But the honest verdict is that this is the component most in need of a reset: load a real font, define a tokenized scale, and delete the dead h1 rules.

---

## 10. Top 5 findings

1. **Blocker — the font never loads.** Zero Inter/Fig Grotesk faces; all text is Segoe UI with synthetic 800/900. The typographic identity is un-delivered (`layout.tsx:1-9`, `package.json`, ground truth).
2. **High — no real type scale.** 13–20px in 1px steps, 20→44 gap, 44/46 h2 collision, 88px hero at 1.91× the section head, emoji thumbs at heading size.
3. **High — UA-default leaks.** No font-size tokens on body/h3/small; the plan page renders 18.72px h3 and 13.33px `<small>` the design never chose.
4. **High — line-height incoherence**, including `font:inherit` forcing `normal` on all form controls (16px text at "normal" vs 24.8px), plus five prose line-heights.
5. **Medium — dead h1 rules.** `main:not(.hero)>h1` (0,1,2) overrides five per-page title clamps, so explore/roadtrip/login/settings/admin all render 62px regardless of intent — and a 62px title sits on a 600px login card.

---

## 11. Confidence: **7 / 10**

**Ground-truth-verified facts (external, measured):** font stack computed as `Inter, "Fig Grotesk", system-ui, sans-serif` with zero loaded Inter faces; the full rendered type scales for landing/plan/explore/roadtrip/login; the 16px "normal" vs 24.8px line-height split; 62px h1 on explore/roadtrip/login; 18.72px h3 and 13.33px small on the plan; rendered lh/ls/weights at every landing size. **Code-verified:** the complete absence of any font-loading mechanism; the `font:inherit` shorthand; the five dead h1 clamps and their specificity math; the UA-default font sizes for h3/small; the 44px emoji thumbs.

**Model-judgment components (not externally measured):** whether Segoe UI's rendering at 0.98 leading actually clips Vietnamese accents (plausible, unproven); the "major-third 13→16→20" reconstruction of author intent; aesthetic severity ratings; the qualitative read that 88px is "slightly overscaled."

**Why not higher (8-9):** the design was inspected only from source and a headless render of the landing and one generated plan — other pages' type was judged from CSS + a sparse render. Whether Inter's 0.98 leading would cleanly render Vietnamese was not verified in-browser. And "beauty" severity is inherently subjective; two of the top findings (F1, F3) are beyond dispute, but the 88px and tracking calls are taste.

**Ground-truth tally:** ~9 externally-verified facts vs ~4 model-judgment items; no counter-evidence encountered for any stated claim.
