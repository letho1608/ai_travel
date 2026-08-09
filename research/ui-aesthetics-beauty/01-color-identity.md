# 01 — Color Identity & Palette Cohesion Audit ("Mình Đi Đâu Thế")

**Lane:** Color harmony, palette cohesion, visual-identity beauty.
**Scope:** `frontend/app/globals.css` (single token file), map components, and hardcoded color usage in `app/*.tsx` and `components/*.tsx`.
**Method:** Full read of globals.css (43 logical lines, sections), grep for every hex/rgba in the frontend, ground-truth pixel histograms (00-ground-truth.md), and computed WCAG/HSV math for every pairing in the token system. No code was modified.

All `globals.css` line references are to the *original* 43-line file section anchors (the file is one declaration per physical line; e.g. line 1 = `:root` tokens, line 43 = the dark override block).

---

## 1. Palette anatomy: what is actually in the box

The token system (`globals.css:1`) contains five functional families:

| Family | Light tokens | Dark tokens | Hue (HSV) |
|---|---|---|---|
| Ink / brand | ink `#2a182e`, ink-2 `#352438`, ink-3 `#4b2c82`, brand `#2a182e`, brand-hover `#352438` | ink `#eae8ea`, ink-2 `#d4d1d5`, ink-3 `#cdb3ff`, brand `#cdb3ff`, brand-hover `#ae86f7` | 262–289 |
| Lavender / accent | accent `#7d4fb8`, accent-2 `#ae86f7`, lavender `#cdb3ff`, lavender-soft `#efe7fd`, lavender-50 `#f7f3fe` | accent `#ae86f7`, accent-2 `#926cd6`, lavender `#cdb3ff`, lavender-soft `#352438`, lavender-50 `#241730` | 261–266 |
| Paper / neutral | paper `#f7f6f3`, surface `#fff`, surface-2 `#fff`, muted `#6f6570`, muted-2 `#948b96`, line `#eae8ea`, line-2 `#d4d1d5` | paper `#141014`, surface `#1f1222`, surface-2 `#2a182e`, muted `#a99fae`, muted-2 `#948b96`, line `#352438`, line-2 `#3d2b42` | 0–300 (near-neutral) |
| Semantic | green `#5fa858`, sun `#f3bd4d`, danger `#bb4d45`, info `#536fac` (+ soft variants) | green `#6fd6a4`, sun `#e6c96a`, danger `#ff9b8a`, info `#93b0e8` (+ soft variants) | 4, 40, 115, 221 |
| Shadow | plum-tinted `rgba(42,24,46,.05–.16)` | pure black `rgba(0,0,0,.4–.6)` | — |

The single most important structural fact: **every chromatic token in the brand system sits at hue 261–266** (accent, accent-2, lavender, lavender-soft, lavender-50, ink-3), with the ink family at 262–289 (plum/magenta-adjacent violet). This is a *mono-hue* violet system with a warm-gray neutral scaffold and four satellite semantic colors. That is a real design decision, not an accident — and it is the key to both the palette's strengths and its weaknesses.

---

## 2. Is the palette aesthetically pleasing and harmonious?

**Verdict: the palette family is genuinely harmonious and tasteful — above the AI-startup median — but it is derivative, and it is structurally under-expressed in the default (light) mode.**

### 2.1 Harmony (strong)

- **One hue family, disciplined.** All lavenders and purples share H≈261–266. Ink `#2a182e` sits at H=289 with S=0.48, V=0.18 — a *slightly* more magenta cast than the accent family. A 23° hue gap between the darkest ink and the accent violet is not a clash; it is precisely what keeps the near-black headings from looking "dead" next to the purple accents. The ink is a plum-black, never pure black — a warm, fashionable editorial choice (visible in the 88px hero heading, `globals.css:13` + `app/page.tsx:31`).
- **Warm/cool equilibrium.** Paper `#f7f6f3` is a *warm* off-white (H=45, S=0.02 — a faint warm cast, not a sterile `#fff`). Pairing warm paper with cool violet is a classic, sophisticated combo. It reads "studio/editorial" rather than "default SaaS."
- **Plum-tinted shadows.** All four light-mode shadow tokens are `rgba(42,24,46,…)` (`globals.css:1`) — shadows tinted by the brand ink instead of neutral black. This is a refined touch most apps skip, and it makes cards sit "in" the brand rather than on top of it.
- **Semantic satellites are coherent.** Gold `#f3bd4d` (H=40), sage `#5fa858` (H=115), dusty red `#bb4d45` (H=4), slate blue `#536fac` (H=221) are all desaturated, dusty tones that sit *inside* the plum/warm-gray world rather than shouting over it. Their soft variants (`green-soft`, `sun-soft`, etc.) are pale pastels that harmonize visually with `lavender-soft`. The gold+plum pairing in particular is a royal, travel-friendly combination — it is just rarely given room to appear.

### 2.2 Derivative-ness (weakness)

- **This is *the* AI-startup purple.** `#7d4fb8 → #ae86f7 → #cdb3ff` is the archetypal "AI gradient" (see the logo, planner stripe, CTA banner, footer mark — `globals.css:4,16,19,37`). A design-savvy observer will immediately classify it: "purple = AI startup." It is competently executed but not a distinctive travel identity on its own.
- **The travel warmth is quarantined.** The sun gold and sage green — the colors that could make this feel like *travel* (dusk gold, roadside green) — appear only as 8px dots (`social-proof .dot`, `globals.css:13`), admin status pills (`globals.css:40`), and spare status text. The *identity* of the app is 100% violet; the travel soul is confined to utility pixels. A designer would call this a palette whose personality comes from one note, and the one note is the most common note in the current AI design zeitgeist.

### 2.3 Gradients — the strongest execution detail

Five gradients exist; four are the same signature sweep (ink-3 → accent → lavender), one is a pastel fade:

1. `.brand::before` 30px logo tile, `135deg ink-3→accent 55%→lavender` (`globals.css:4`) — the brand mark. In light mode: deep violet `#4b2c82` → royal `#7d4fb8` → light lavender `#cdb3ff`. Beautiful, cohesive, a genuinely nice logo tile.
2. `.planner::before` 6px top stripe, `90deg ink-3→accent→lavender` (`globals.css:19`) — a thin brand accent on the hero widget. Good.
3. `.cta-banner`, `135deg ink-3→accent 60%→accent-2` (`globals.css:16`) — the big saturated moment. Good in light mode.
4. `.footer-brand::before`, `135deg accent-2→lavender` (`globals.css:37`) — a pale variant that keeps the footer mark lighter than the nav mark. Thoughtful variation.
5. `.featured-card .thumb`, `135deg lavender-soft→lavender` (`globals.css:16`) — pale pastel thumbnail field for emoji. Fits.

**The problem:** in dark mode, `--ink-3` becomes `#cdb3ff` and `--accent` becomes `#ae86f7` (`globals.css:43`), so gradients 1–3 collapse to a *light-lavender-to-light-lavender* fade (see §8.2). The single most distinctive brand artifact — the deep-violet-to-lavender sweep — only exists in light mode.

---

## 3. Saturation evidence: is light mode too timid?

Ground truth (00-ground-truth.md §8): light-mode screenshots show `mean_sat 0.030–0.053`, with 94–96% of pixels bright and top color `#e0e0e0` at ~95%. Dark mode shows `mean_sat 0.26–0.33` with lavender visible as `#c0a0e0`.

**Important correction to the framing:** the *tokens* are not low-saturation. `accent #7d4fb8` has S=0.57, `lavender #cdb3ff` S=0.30, `sun #f3bd4d` S=0.68. The mean saturation is low because **95% of rendered pixels are paper/white/surface** (`#f7f6f3` S=0.02, `#fff` S=0, `line #eae8ea` S=0.01) and the saturated tokens are deployed in *tiny areas*.

So the honest diagnosis is not "the palette is faded" — it is "**the light design spends its color budget in sprinkles.**" Auditing where lavender actually appears in light mode:

- The 30×30px logo tile (`globals.css:4`)
- The 6px planner stripe (`globals.css:19`)
- Three pale thumbnail fields on the landing (`globals.css:16`)
- Pale `lavender-soft`/`lavender-50` chips, bubbles, tab backgrounds (near-white pastels, S=0.09)
- The CTA banner — the *one* large saturated element — sits below the fold (`globals.css:16`)

Above the fold on the landing, the user sees: warm paper, a giant plum-black headline (which reads as *ink*, not color), a pale chat bubble, and a few lavender-soft chips. The result — 95% near-white pixels, mean_sat 0.036 — is a light mode that **under-serves its own identity**. A travel product asking people to "plan their trip" ships its color story in a thimble. This is the single biggest beauty gap in the app, and it is a *coverage/ambition* problem, not a token-saturation problem. Fixing it is easy (more lavender surface, a saturated hero moment, colored featured-card fields) — which makes its absence all the more noticeable.

That said, fairness: there is a defensible aesthetic argument for the calm editorial look. The light mode is *not ugly* — it is coherent, warm, and clean. It is just *polite to the point of blandness*, and for a category as emotional as travel, bland is a bigger sin than loud.

---

## 4. Color pairings audit (contrast math, verified)

Computed WCAG contrast ratios (my math, not the prior deep-dive):

| Pairing | Ratio | Where | Verdict |
|---|---|---|---|
| accent `#7d4fb8` on paper | 5.28 | links, `.eyebrow`, `.status` (`globals.css:10`) | Good |
| brand `#2a182e` on paper | 15.32 | headings, `.step::before` | Excellent |
| ink on paper | 15.32 | body text | Excellent |
| muted `#6f6570` on paper | 5.15 | `.lead`, `.nav-links`, secondary text | Good |
| **muted-2 `#948b96` on paper** | **3.04** | `.disclaimer`, `.source`, small print (`globals.css:10,25`) | **Fails AA for small text — too faint** |
| danger `#bb4d45` on paper | 4.56 | `.error`, `.danger-zone h2` | Borderline AA (large/bold only) |
| green `#5fa858` on paper | 2.69 | `.social-proof .dot` (non-text) | OK as a graphic; would fail as text |
| sun `#f3bd4d` on white | 1.72 | accents only | OK (never text on white) |
| ink-3 `#4b2c82` on white | 10.60 | `.cta-banner .primary` label | Excellent |
| lavender `#cdb3ff` on paper | 1.69 | — (only used *on* dark surfaces) | N/A |
| accent-2 `#ae86f7` on paper | 2.57 | `:focus-visible` outline (`globals.css:1`) | Borderline (3px ring mitigates) |
| ink `#2a182e` on lavender | 5.80–9.06 | dark primary buttons, selection | Good |

### 4.1 The `muted` vs `muted-2` question (asked directly)

Light: `#6f6570` (S≈0.07, dark gray-plum) vs `#948b96` (lighter gray), luminance ratio 0.51 — clearly distinguishable, correct hierarchy. Dark: `#a99fae` vs `#948b96`, luminance ratio 1.35 on `#141014` — both are mid lavender-grays; contrast 7.41 vs 5.74. **Distinguishable, but only just, and the hierarchy muddle is real:** on a dark UI these two "gray" levels are a hair apart, and `--muted-2` is the *only* token unchanged across both modes (`#948b96` in both). It reads as a deliberate gray that works everywhere, which is fine — but in dark mode the gap between "muted" and "muted-2" nearly vanishes, so disclaimer-level text loses its visual quiet. Low severity.

### 4.2 Accent-2 `#ae86f7` vs `#926cd6` (asked directly)

These two are not a light/dark pair — they are light-mode `accent-2` and dark-mode `accent-2` respectively. In light, accent-2 (`#ae86f7`) is *lighter* than accent (`#7d4fb8`). In dark, accent-2 (`#926cd6`) is *darker* than accent (`#ae86f7`). **The relative hierarchy inverts across modes.** Since accent-2 is only used for focus outlines (`globals.css:1`) and gradient end-stops (`globals.css:16,37`), the inversion is not visible as a bug, but it is a semantic inconsistency: "the secondary accent" changes meaning with the theme. Combined with the token collisions in §8.3, the dark mode has less *color vocabulary* than light mode.

### 4.3 Semantic colors on their soft fills (admin pills, `globals.css:40`)

`ready` → green-soft `#e3efe0` + `#28491f` (≈11:1), `mock` → sun-soft `#f4e9d3` + `#5c3a0e` (≈8:1), `down` → danger-soft `#f0dad7` + `#5c1a14` (≈8:1). These are the best-executed pairings in the file — properly contrast-managed in *both* modes with explicit overrides at `globals.css:43`. Whoever wrote these knew what they were doing.

---

## 5. Do light and dark feel like the same brand?

**Largely yes — the hue identity survives the inversion, with two structural wrinkles and one outright break.**

The dark override block (`globals.css:43`) is a *luminance inversion* of the same violet system, not a different palette:

- Every dark surface is plum-tinted, not neutral: paper `#141014`, surface `#1f1222`, surface-2 `#2a182e`, line `#352438`, lavender-soft `#352438`, lavender-50 `#241730`. Dark mode *lives in the plum world*. This is what keeps the two modes feeling like one product — and it is genuinely well done.
- `brand` inverts to `#cdb3ff` (lavender buttons, plum text) — a defensible, common trick. Dark primary buttons are lavender with near-black labels at 9.06:1. Strong.
- Semantic colors all lighten predictably (green `#5fa858→#6fd6a4`, danger `#bb4d45→#ff9b8a`, sun `#f3bd4d→#e6c96a`, info `#536fac→#93b0e8`) — the correct direction for dark surfaces, and their soft fills flip correctly too.
- Shadows switch from plum-tinted to black (`globals.css:43`) — appropriate (light shadows would glow wrongly on dark).

**Where identity cohesion wobbles:**

1. **`--ink-3` is semantically re-purposed.** In light, ink-3 `#4b2c82` is the "deep purple" step of the ink family. In dark it becomes `#cdb3ff` — literally the *lavender* token. This is a deliberate "purple step turns light" mapping that *almost* works (it makes the gradients re-tint) but it silently breaks `::selection` (see §8.1).
2. **`--accent-2` hierarchy inversion** (§4.2).
3. **Token collisions in dark mode:** `--brand` = `--lavender` = `--ink-3` = `#cdb3ff`, and `--lavender-soft` = `--line` = `#352438`. In light mode these are five distinct colors; in dark mode they collapse into two. The *gradient sweep* (deep violet → royal → lavender) that defines the light identity literally cannot exist in dark mode — the dark gradients are lavender-to-lavender (see §8.2).
4. **The footer's identity anchor disappears in dark.** In light, `.site-footer` is a deep-plum ink block against warm paper — the single strongest brand statement on any page (`globals.css:37`, and the cause of the "37% dark" pixel blocks on history/login screenshots). In dark it becomes `surface-2 #2a182e` against `#141014` — a *slightly lighter* box that visually dissolves into the page. The one moment of brand bravado is muted to near-invisibility in dark mode. Not a bug; a missed opportunity.

**Bottom line:** same brand, two intensities. Light mode is the *muted* expression (ink on warm paper), dark mode is the *saturated* expression (plum world + glowing lavender). If anything, dark mode is the more beautiful of the two — which is backwards for a product whose default experience is light.

---

## 6. Dark-mode breakages (real, code-verifiable)

### 6.1 `::selection` is invisible in dark mode — HIGH

`globals.css:1`: `::selection{background:var(--lavender);color:var(--ink-3)}`.
`globals.css:43`: `--ink-3:#cdb3ff` and `--lavender:#cdb3ff`.

In dark mode the selection background *and* the selection text are both `#cdb3ff`. **Selected text renders as lavender-on-lavender — completely invisible.** In light mode the pairing is `#4b2c82` on `#cdb3ff` (5.80:1, fine). The rule was simply never re-mapped in the dark block. This is a real, reproducible defect, both an accessibility failure and an aesthetic one (users who highlight text in dark mode get a filled box with no text).

### 6.2 Dark-mode CTA banner is a broken light-box — HIGH

`globals.css:16`: `.cta-banner` gradient `ink-3→accent 60%→accent-2` with `h2{color:#fff}`, `p{color:rgba(255,255,255,.85)}`, and `.cta-banner .primary{background:#fff;color:var(--ink-3)}`.
`globals.css:43` does **not** override the CTA banner, and the generic `.primary{background:var(--brand)}` override loses on specificity to `.cta-banner .primary` (0,1,0 vs 0,2,0).

In dark mode the banner therefore becomes a **light-lavender gradient box** (`#cdb3ff → #ae86f7 → #926cd6`) carrying **white text**: the h2 measures 1.83:1 at the light end and 3.93:1 at the dark end (fails even large-text thresholds at the start), the paragraph is worse, and the button is white with a lavender label (`#cdb3ff` on `#fff` = **1.83:1** — nearly unreadable). Visually, it is the one element that actively fights the dark theme: a glowing pastel rectangle in a plum-black app. Whoever adds dark support next should map the gradient to dark-surface colors and flip the text/button to dark-on-light.

### 6.3 Dark gradient collapse (linked to 6.2) — MEDIUM

Because `ink-3`, `accent`, and `lavender` all land in the `#ae86f7–#cdb3ff` range in dark mode, the logo tile, planner stripe, and CTA banner lose the violet sweep. In dark the logo is a uniform pale-lavender tile — a *fine* mark, but it is a different logo than the light one. This is the concrete cost of `ink-3 → #cdb3ff` and `accent-2 → #926cd6`.

---

## 7. Hardcoded colors that break cohesion (asked directly)

Component/page files are clean: `app/page.tsx`, `app/plan/[token]/page.tsx`, `app/admin/page.tsx`, `app/history/page.tsx`, `app/login/page.tsx`, and all components use classes only. The only hardcoded colors live in two map components and a scattering of `#fff`s inside globals.css.

### 7.1 The map teal/orange — the cohesion breaker — HIGH

`components/MapView.tsx:37`: `color: slot.dia_diem_id === selectedId ? "#e4572e" : "#0f766e"`
`components/MapView.tsx:49`: `L.polyline(points,{color:"#0f766e",weight:4})`
`components/RoadTripMap.tsx:15-16`: `color:"#0f766e"` and `index===0 ? "#e4572e" : "#0f766e"`

These are the old brand colors — the `.next-build-check`/`.next-final-check` build artifacts still show the *previous* identity: `:root{--brand:#0f766e;--paper:#fffdf7;--sun:#f3bd4d}`. So the app's two most content-rich pages (plan workspace, roadtrip builder) paint their route lines and markers in **teal (`#0f766e`, H=175) and orange (`#e4572e`, H=14)** — hues that exist nowhere else in the current violet system. Teal-adjacent-to-purple is a cool/high-chroma intruder; orange-adjacent-to-purple is a complementary clash. On the plan page (dark mode especially) you get plum UI framing a bright OSM map crisscrossed in teal and orange that belonged to a different brand. This is the single clearest palette-cohesion violation in the app, and it is invisible in the token file — it only shows up in the grep. It is also trivially fixable (map `#0f766e → var(--accent)`-equivalent, `#e4572e →` a warm sun/brand contrast).

### 7.2 White/other hardcoded values inside globals.css — LOW

- `#fff` on `.danger` (`globals.css:7`), `.chat-box button` (`globals.css:22`), `.cta-banner` block (`globals.css:16`), `.footer-brand`/`.footer-col h4` (`globals.css:37`), plus `rgba(255,255,255,.85)` and `rgba(255,255,255,.12)` in the CTA/footer. All are overridden where needed in the dark block, so none are *bugs* — but they are untokenized, which means any future palette shift silently misses them.
- `.danger:hover{background:#a03a33}` (`globals.css:7`) — a fixed hover shade of the danger red, not derived from the token. It darkens correctly for light mode but in dark mode the generic `.danger:hover` override at `globals.css:43` replaces it (`--danger-soft` bg) — so this hardcode is only "active" in light mode. Fine, but fragile.
- Nav backgrounds `rgba(247,246,243,.86)` / `rgba(20,16,20,.78)` (`globals.css:4`) — hardcoded paper/ink alpha instead of `var(--paper)`; token hygiene nit.
- Shimmer highlight `rgba(255,255,255,.5)` (`globals.css:25`) — correct as white shimmer in both modes, fine.
- Admin pill text colors `#28491f / #5c3a0e / #5c1a14` with explicit dark counterparts `#6fd6a4 / #e6c96a / #ff9b8a` (`globals.css:40,43`) — properly done, hardcoded but fully mirrored.
- `.text-muted{color:var(--muted)}` is defined **only inside the dark block** (`globals.css:43`) and referenced nowhere in `*.tsx` — a dead, asymmetric token exposure.

---

## 8. The visual identity verdict (designer's honest take)

If I were reviewing this as a brand design handoff:

**What's good.** The palette has a real point of view: a disciplined violet monochrome on warm paper, plum-tinted shadows, an editorial plum-black ink for type, and a coherently-inverted dark mode. The token structure is honest and legible. The gold-with-plum latent combination is genuinely lovely and underused. The light-mode footer (deep plum block on warm paper) is the most confident color moment in the app.

**What's generic.** "Lavender + purple gradient + warm gray" is 2024–26 *default AI startup*. Nothing about it says "Vietnam," "travel," or "getting lost somewhere beautiful." The two travel-native colors in the box (sun gold, sage green) are rationed to status dots and admin pills. A distinctive travel identity would let the dusk-gold and roadside-green share the stage with the violet instead of hiding behind it.

**What's broken.** Dark mode has an invisible selection highlight, a glowing light-box CTA banner with illegible white text, and a gradient language that collapses into one flat lavender. The maps still wear the previous brand's teal and orange. And light mode — the mode 95% of visitors will see — resolves to 95% near-white pixels with the palette in sprinkles.

**Score out of 10 for "distinctive beauty":** the *palette system* is a 6.5–7/10 (harmonious, tasteful, slightly derivative); the *rendered light experience* is a 4/10 (timid, near-monochrome); the *dark experience* is a 7.5/10 (plum world, glowing lavender, but with the CTA/selection bugs); the *cohesion across everything* is a 5.5/10 because of the map colors and the two-mode gradient collapse.

---

## 9. Findings by severity

### High

- **H1 — Maps hardcode the previous brand (teal `#0f766e`, orange `#e4572e`), clashing with the violet identity.** `components/MapView.tsx:37,49`; `components/RoadTripMap.tsx:15-16`. Visible on the two most content-rich pages; hues 175/14 vs the system's 261–289. Cleanest possible cohesion break, trivially fixable, zero tokens involved.
- **H2 — Dark-mode `::selection` is invisible (lavender text on lavender background).** `globals.css:1` + `globals.css:43` (`--ink-3:#cdb3ff`). Reproducible on any text highlight in dark mode; both a11y and aesthetic defect; no dark override for the rule.
- **H3 — Dark-mode CTA banner is a light-lavender box with white text (1.83–3.93:1) and a white button whose label is lavender-on-white (1.83:1).** `globals.css:16` (no override at `globals.css:43`; specificity loss for the generic `.primary` fix). The one element that actively fights the dark theme.
- **H4 — Light mode under-serves its palette: 95% near-white pixels, mean_sat 0.030–0.053; lavender confined to sprinkles.** Ground truth §8; code audit confirms saturated tokens cover <5% of light-mode surface. A coverage/ambition gap, not a token-saturation gap. The default experience is *polite, not beautiful*.

### Medium

- **M1 — Dark-mode gradient collapse + `--accent-2` hierarchy inversion.** `globals.css:43` (`ink-3→#cdb3ff`, `accent-2→#926cd6`). The light identity's signature violet sweep becomes a flat lavender fade in dark; the "secondary accent" flips relative to accent between modes.
- **M2 — Dark-mode token collisions blur distinctions.** `--brand = --lavender = --ink-3 = #cdb3ff` and `--lavender-soft = --line = #352438` (`globals.css:43`); adjacent nav active/CTA states become identical, and five distinct light colors collapse to two in dark.
- **M3 — Inputs/cards are white-on-white with hairline borders in light mode.** `--surface = --surface-2 = #fff` and `--line #eae8ea` ≈ 1.13:1 on paper (`globals.css:1,19,25`). Contributes directly to the washed-out screenshot feel (plan/explore at 90–96% bright). Color-adjacent to the component lane.

### Low

- **L1 — `muted-2 #948b96` at 3.04:1 on paper for small print (`.disclaimer`, `.source`); in dark the muted/muted-2 gap nearly vanishes (lum ratio 1.35).** `globals.css:1,10,25,43`.
- **L2 — Untokenized `#fff`/`rgba(...)` literals** in `.danger`, `.chat-box button`, `.cta-banner`, footer, nav alpha backgrounds (`globals.css:4,7,16,22,37`) — override-safe today, fragile tomorrow.
- **L3 — `.text-muted` defined only in the dark block, referenced nowhere** (`globals.css:43`) — dead, asymmetric.
- **L4 — `.danger-zone h2` at 4.56:1 and `green` at 2.69:1 on paper** are borderline/fail for text-size usage (`globals.css:10,34`).

### Notes (strengths)

- **N1 — The palette family is genuinely harmonious**: mono-hue violet (H 261–266), warm paper (H=45), plum ink (H=289), plum-tinted shadows, coherent dusty semantics. Above the startup median.
- **N2 — The light-mode footer plum block is the best single color moment** (`globals.css:37`); it should be *repeated*, not hidden in dark mode.
- **N3 — Dark mode is the stronger expression** (saturation 0.26–0.33, glowing lavender on plum) — the identity lives where fewer users are.
- **N4 — Purple is derivative for the category**; the sun-gold/sage travel warmth is under-deployed (admin pills only).

---

## 10. Executive summary (250 words)

The color system behind "Mình Đi Đâu Thế" is a disciplined, genuinely harmonious violet-on-warm-paper design: every brand token sits in one hue family (261–266°), the ink is a plum-black rather than dead black, shadows are plum-tinted, the warm-gray paper pairs with the cool lavender beautifully, and the dark mode is a well-executed luminance inversion that stays inside the same plum world. These are the marks of a designer, not a template. But the beauty does not survive contact with the rendered pages. Light mode — the default — resolves to 95% near-white pixels with mean saturation 0.03–0.05: the lavender appears in sprinkles (a 30px logo tile, a 6px stripe, pale chips), and the one saturated block sits below the fold. It reads polite and bland, not beautiful. Worse, cohesion is punctured in three concrete places: the maps still draw in the *previous* brand's teal and orange (the old identity's `#0f766e` survives in two components); dark mode's text-selection highlight is invisible lavender-on-lavender; and the CTA banner stays a light-lavender light-box with white text and a lavender-on-white button label in dark mode. The gradient language itself collapses in dark mode because `ink-3` re-maps to lavender. The palette is tasteful but derivative (classic AI-startup purple, with the travel-native gold and sage quarantined to status dots), and the dark experience is arguably the more beautiful one. Fix the map colors, the selection rule, and the dark CTA; give light mode real color coverage; and this becomes a genuinely distinctive travel identity.

---

## 11. Top 5 most concerning findings

1. **Legacy brand colors still live in the maps.** Teal `#0f766e` and orange `#e4572e` on the plan and roadtrip pages (`components/MapView.tsx:37,49`; `components/RoadTripMap.tsx:15-16`) clash with the entire violet system — a direct palette-cohesion violation on the app's two busiest screens.
2. **Dark-mode `::selection` renders invisible** — lavender text on lavender (`globals.css:1` + `globals.css:43`). Every text highlight in dark mode disappears.
3. **Dark-mode CTA banner is illegible and off-theme** — white text on a light-lavender gradient (1.83–3.93:1) and a white button with lavender label (1.83:1) because no dark override exists and specificity blocks the generic fix (`globals.css:16,43`).
4. **Light mode hides its own identity.** 95% of rendered pixels are near-white (mean_sat 0.03–0.05); the saturated tokens cover <5% of the surface. The default experience is colorless — a coverage failure, not a token-saturation one.
5. **Dark mode's gradient identity collapses.** `--ink-3 → #cdb3ff` and `--accent-2 → #926cd6` flatten the logo/planner/CTA violet sweeps into a uniform pale lavender, and several tokens collide (`brand = lavender = ink-3`), blurring the distinctions the light palette carefully maintains.

---

## 12. Confidence rating

**7 / 10.**

Reasoning: High confidence (≥9) on the code claims — every hex, pairing, and specificity argument was verified directly against `globals.css`, the two map components, and computed WCAG math, and the ground-truth pixel histograms independently confirm the light-mode paleness (95% bright, mean_sat 0.03–0.05). Moderate-to-high confidence (8) on the dark-mode defects, since the pixel data captured dark mode as deep black and lavender (`#c0a0e0`) consistent with the token remap, but the exact rendered CTA-banner appearance depends on the emulation caveat noted in 00-ground-truth.md (computed styles vs pixels disagreed), so I rely on specificity analysis rather than a screenshot. Lower confidence (5–6) on the *subjective beauty judgments*: calling light mode "timid" versus "intentionally minimal" is a taste call — the palette is unambiguously harmonious, but whether that harmony is distinctive or derivative for a travel brand is genuinely debatable. No live rendering was performed in this lane, so visual-warmth judgments lean on ground-truth statistics and color science rather than first-hand screenshots. Ground-truth tally: **6 externally-checked facts** (saturation metrics, pixel quantizations, code tokens, contrast ratios, gradient definitions, hardcoded-color inventory) vs **4 model judgments** (derivative-ness, editorial intent, dark-is-more-beautiful, map-color clash severity).
