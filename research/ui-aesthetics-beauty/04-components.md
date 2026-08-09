# Component Craftsmanship — micro-visual polish of buttons, cards, chips, bubbles, inputs, icons, shadows, radii, hover/transition states

**App**: "Mình Đi Đâu Thế" (Next.js 15, `frontend/`)
**Lane**: Component craftsmanship (micro-detail of individual UI elements). NOT color system, typography, or page composition — those belong to the other 4 agents.
**Sources read**: `frontend/app/globals.css` (43 minified lines, all fully expanded), `frontend/components/{Planner,PlanView,MapView,RoadTripMap,Navigation,Footer}.tsx`, `frontend/app/{page,login,settings,history,support,explore,roadtrip,admin,plan/[token]}.tsx`, `frontend/app/layout.tsx`, `frontend/lib/roadtrip-translations.ts`, `node_modules/leaflet/dist/leaflet.css`, plus ground truth `00-ground-truth.md` and prior audit `research/ui-aesthetics/03-components.md` + `09-fixes-applied.md` for continuity.
**Method**: static code audit cross-checked against the browser-rendered radii/shadow facts in the ground-truth file. Research only — no code changes.

---

## Executive summary of the lane

The component layer has a real, opinionated craft voice: tokenized radii (8/12/16/24/32/999), a four-step shadow scale, a coherent 120–200ms `cubic-bezier(.4,0,.2,1)` motion language, and several genuinely lovely micro-details (the 6px halo on `.assistant-dot`, the 4px lavender ring on a selected `.slot`, the dashed border that marks "stale" data in `.last-updated`, the mirror-symmetrical 6px chat tails). That voice, however, is enforced only at the *token* layer, not the *component* layer. Anywhere a component consumes the tokens, it improvises a variant: there are four button heights, four input paddings, six card paddings, three hover-lift amplitudes, two tab dialects, two send-button opacity values for the same button, and one entire section (admin booking queue) that silently lost its `.card` class and renders as raw text. The system reads as "designed, then not coordinated." Individually each component is competent and modern; collectively they fragment. The single most damaging craft decision is `.primary{width:100%}` baked into the base button (globals.css:7), which forces every context to fight the default and produced exactly the admin-card bug in the first place.

Verdict: strong micro-details, weak micro-consistency. **6.5/10.**

---

## 1. Buttons — pill body is tasteful; size discipline is broken

### The shared body is good
`.primary,.secondary,.danger` (globals.css:7) share one geometry: `display:inline-flex`, `border-radius:999px`, `padding:13px 24px`, `font-weight:800`, `font-size:15px`, `border:2px solid transparent`. The transparent 2px border on `.primary`/`.danger` is a thoughtful detail — it guarantees identical heights with the 2px-bordered `.secondary`, so a primary and secondary sitting side by side (settings delete/cancel, roadtrip add-stop/build) align perfectly. The `translateY(-1px)` + `shadow-sm→md` hover is restrained and premium, the kind of "lift" used by Stripe/Vercel-class UIs. `font-weight:800` on a pill with 999px radius is the current mainstream "AI app" dialect — tasteful, but generic (ChatGPT, Claude, Perplexity all do this). It does not feel cheap; it feels *safe*. The `:disabled{opacity:.5}` is standard and fine.

### The problems

**No size scale exists — four heights are fabricated ad hoc.**
- Base pill: 13px/24px padding + 15px font + 2px borders ≈ **53px** tall.
- `.inventory-search .primary{height:46px}` (globals.css:28) and `.admin-catalog-form .primary,.secondary{height:46px}`, `.admin-plan-form .primary{height:46px}` (globals.css:40) — a second height created by forcing `height` instead of adjusting padding.
- `.comment-form .primary{padding:11px 20px}` (globals.css:25) — a third, unnamed variant.
- `.retry-action{padding:8px 16px}` (globals.css:10) — a fourth, "mini pill."
- `.trip-actions .icon-action{height:38px}` (globals.css:25) — a fifth, and this one is **dead CSS**: no `.icon-action` exists inside `.trip-actions` (PlanView.tsx:121 uses nine `.secondary` buttons there). The intent was clearly a compact 38px header-action row; the reality is nine ~53px pills stacked under the title.

Net effect: on the plan page header you get nine full-height pills; on the same page's forms the send button is a 46px circle; on settings a 53px primary; on explore/admin a 46px primary. A user clicking through the app sees buttons that are the same component at four different sizes with no rule explaining why.

**`.primary{width:100%}` is a footgun as a default** (globals.css:7). Every context must opt out: `.roadtrip-actions .primary{width:auto;margin-left:auto}` (globals.css:31), `.cta-banner .primary{width:auto}` (globals.css:16). This is the same latent bug class that already fired once (admin booking card). The CTA banner also inherits this and is only rescued by an override. `width:100%` belongs on a `.form-submit` utility, not the button base.

**`.secondary`'s 2px border is heavy.** At 53px tall with `border:2px solid var(--line-2)`, the outline reads chunkier than the 1px-bordered cards and inputs around it. It is deliberate (height parity) but visually it makes secondary actions look like they have more weight than the primary, which is inverted hierarchy. A 1px border + adjusting padding (14px) would preserve parity and lighten the look.

**`.danger` is the weak sibling.** Solid `#bb4d45` pill with white text is fine; the hover is just a darker fill (`#a03a33`, globals.css:7) with no shadow step, so it lacks the tactile progression of the other two. In dark mode it was fixed (T0-1) to `var(--brand-contrast)` on `#ff9b8a` — now correct.

**Cross-page body consistency is otherwise good**: the same `.primary`/`.secondary` are reused everywhere (explore:66, admin:362/507/591, history:55, settings:37, login:72), which is the strongest argument that the *token* story works.

---

## 2. Radii system — a sound scale, poorly governed at the edges

The scale itself is defensible: `--radius-xs:8, sm:12, md:16, lg:24, xl:32, full:999` (globals.css:1) — a gentle 4px Fibonacci-ish ramp. The *assignments* are not governed.

**Where the odd rendered radii come from (ground truth #1 "radii … 4px … mixed 16px-6px … 32px-32px-0"):**
- **4px / 3px / 5px are Leaflet's defaults**, confirmed in `node_modules/leaflet/dist/leaflet.css` (4px zoom-control buttons + 3px tooltip + 5px attribution). The app overrides only the popup (`.leaflet-popup-content-wrapper{border-radius:var(--radius-sm)}`, globals.css:40). So on the plan map you get: 24px map container → 12px popup → **4px zoom buttons** → 10px attribution text. The 4px controls are intentional (Leaflet), but they are *unreconciled* — nothing else in the app uses 4px, and the zoom buttons visibly sit at the bottom of a 12/16/24px ecosystem. Either accept them as "map chrome" (defensible) or theme them up to 8px.
- **mixed 16px-6px** = chat bubbles (globals.css:22): `radius-md` on three corners, 6px on the "tail" corner. Confirmed.
- **32px-32px-0** = `.site-footer` (globals.css:37): `radius-xl radius-xl 0 0`, a full-bleed dark slab with rounded top — intentional and handsome.
- **50%** = stop-index, social-proof dot, assistant-dot, spinner, typing dots, `.stop-input>span`, `.chat-box button`.

**Pill overuse is real but not fatal.** Counting every 999px element: primary/secondary/danger, icon-action, chip, nav-links, nav-cta, day-tabs, inventory-tabs, trip-facts pills, admin-pill, admin-tags, price-analysis spans, chat-box input, chat-box button, hero eyebrow. That is the entire interactive vocabulary. The danger isn't "too round" — it's that **pill radius is applied uniformly to three different weights** (primary CTA, passive info tag, selected tab, text input), so hierarchy relies entirely on color/size, and pills stop communicating "kind of element." The `trip-facts span` (passive data, globals.css:25) and the primary CTA sharing the same 999px shape is where "samey" bites. The step badges partially rescue this by using square 12px (`step::before` 40px r12, globals.css:16) — but then the *same numbering concept* on the plan page is a 28px circle (`.stop-index`) and on roadtrip a 30px circle (`.stop-input>span`). Three number badges, three shapes/sizes.

**Radius discipline within surfaces is loose**: `.card` = lg24, `.planner` = xl32, `.faq-item` = md16, `.slot` = md16, `.comment` = sm12, `.map-legend` = sm12. A page can show three different corner radii on "same-rank" boxes. The scale is fine; the rule "which rank gets which radius" does not exist.

---

## 3. Shadows — subtle and premium in light; the "dark shadows in light screenshots" is a measurement artifact

**Verified resolution of the ground-truth puzzle.** The ground-truth file (items 6, 10) captured computed `box-shadow` values of `rgba(0,0,0,.4–.6)` (dark tokens) while the *pixels* were light. I checked the only place dark shadows exist: `@media(prefers-color-scheme:dark){:root{--shadow-sm:0 1px 2px rgba(0,0,0,.4);…--shadow-xl:0 32px 80px rgba(0,0,0,.6)}}` (globals.css:43). Light `:root` tokens (globals.css:1) are `rgba(42,24,46,.05–.16)`. There are **no hardcoded shadow values anywhere** outside the two token blocks (all component rules use `var(--shadow-*)` or the lavender ring `0 0 0 4px var(--lavender-soft)`). **Conclusion: a light-mode page cannot render dark shadows in the shipped code.** The capture was the CDP emulation ambiguity the ground truth itself flags — computed styles ran under dark emulation while screenshots rendered light. Not a code defect.

**Honest assessment of the light shadows:** the scale is well-built — `sm 1px/2px @ .05`, `md 2px/8px @ .07`, `lg 18px/50px @ .12`, `xl 32px/80px @ .16`. `lg`/`xl` are genuinely soft and premium (planner on landing, cta-banner). But `sm` (the card default) at 0.05 alpha over 1–2px is **practically invisible**, and the card border `--line:#eae8ea` (globals.css:1) on paper `#f7f6f3` is ~3.5% contrast — also nearly invisible. Result: in light mode cards are defined almost entirely by radius + surface white, which is why the ground-truth pixels read 95% white/`#e0e0e0` and "extremely low-color, mostly whitespace." The app *leans flat* not by choice but because the two cheapest separation tools (border, sm shadow) are tuned too faint. This is the single biggest "premium vs flat" lever in the component layer: either darken `--line` slightly or bump `sm` to ~0.08 with a 1px Y offset. The dark-mode shadows (0.4–0.6 alpha) are extremely dark but functionally fine — on `#141014` surfaces they mostly add soft depth, and the values are appropriate for OLED-ish dark UIs.

The lavender **rings** (focus `0 0 0 4px lavender-soft`, slot-selected, assistant-dot halo, social-proof dot) are the app's real "shadow language" and are lovely — a soft color halo instead of gray occlusion. Keep them.

---

## 4. Micro-interactions — coherent motion, missing press states

**The motion language is consistent and good**: everything moves on `cubic-bezier(.4,0,.2,1)` with durations chosen by property — 120ms for transform, 150ms for background/color/border, 200ms for box-shadow. Lifting (buttons -1px, slot -1px, featured-card -4px, timeline card -2px), scaling (icon-action 1.06/0.94, chat send 0.94), and color fades all read as one family. `prefers-reduced-motion` is respected globally (globals.css:1). This is the most polished axis of the whole component system.

**Gaps:**
- **No `:active` press feedback on pills.** `.icon-action:active` has `scale(.94)` (globals.css:7) and `.chat-box button:active` has `scale(.94)` (globals.css:22) — but `.primary/.secondary/.danger` and `.chip` have **no `:active` state at all** (globals.css:7). A 53px pill that lifts on hover but does nothing on press feels less "alive" than the circles that do. One shared `:active{transform:translateY(0);scale:.99}` for the pill trio would unify it.
- **Lift amplitudes disagree**: -1px (buttons, slot) vs -2px (`.timeline a.card`, globals.css:34) vs -4px (`.featured-card`, globals.css:16). Same semantic "lift," three distances. The featured-card -4px is fine for a large card; the timeline -2px should be -1px to match slots.
- **Disabled opacity is inconsistent for the identical control**: `.chat-box button:disabled{opacity:.5}` (globals.css:22) but `.planner .chat-box button:disabled{opacity:.55}` (globals.css:19) — the send button on the landing planner dims to .55, on the workspace to .5.
- **Hover affordance asymmetry**: chips get full hover (border+bg), inventory-tabs hover only changes border-color (globals.css:28), day-tabs only background (globals.css:25), inputs have no hover border change at all outside planner (still, from the prior audit, most inputs only react on focus). The "touchable" feeling is strongest in the planner/workspace and weakest in explore/roadtrip forms.

**State machinery worth praising**: `.slot.selected` ring + border + shadow; `.chip[aria-pressed="true"]` solid-fill active (correct a11y semantics wired to visuals); `.comment.resolved` at opacity .58 with line-through; `.notification.read` at .62. These are exactly the right "state = visual" craft.

---

## 5. Chat bubbles, typing indicator, spinner

**Bubbles (globals.css:22):** assistant `lavender-50` + `1px lavender-soft` border; user solid `--brand`. The 6px "tail" corner (bottom-left/bottom-right respectively) creates a perfect mirror asymmetry. Verdict on "refined or dated": **competent, slightly hand-rolled.** The 6px-against-16px corner is the cheapest CSS approximation of a tail — it produces a slightly lopsided inner corner, and against the 1px border the tail reads as a "notched" corner rather than a deliberate tail. Modern chat UI (Linear, iMessage, modern WhatsApp) uses either no tail, a small square tail, or a proper SVG triangle; the 16px/6px asymmetry is the one component that betrays "CSS-first, no icon/illustration budget." It is not ugly — it is *recognizable as a shortcut*. Also worth noting: `bubble.user` has no border while `bubble.assistant` has one, which makes the user bubble look slightly larger/weightier (border + surface color vs flat brand). Fine, but it's an asymmetry nobody decided on.

**Typing indicator:** `.bubble.typing` (7px dots, 1.2s `typingPulse` with -3px bounce and staggered delays, globals.css:22) is genuinely polished — but **it is never rendered anywhere** (grep of all `.tsx` shows only `bubble assistant` and `bubble ${item.role}`; the role values are "assistant"/"user"). The app's busy state is the spinner+text row in PlanView.tsx:123 and plain status text in Planner. Beautiful micro-interaction, shipped dead.

**Spinner:** 16px, 2px `lavender-soft` track with `accent` top arc, 0.8s ease — clean, appropriately small for an inline status row (PlanView.tsx:123). Polished. At 16px it reads as "working" without shouting. Good.

**`assistant-dot`:** 12px accent circle + `0 0 0 6px lavender-soft` halo (globals.css:22), used identically in the planner welcome (Planner.tsx:161) and the workspace panel title (PlanView.tsx:127). This is the best micro-detail in the app — a soft "presence" glow that gives the chat identity. Keep as-is.

---

## 6. Inputs — square vs pill in the same form, four paddings

**Mixed metaphor confirmed.** Inside the single planner card you have: a **pill** `.chat-box input` (`radius-full`, padding 12px 18px, globals.css:22) and directly beneath it a **radius-sm** `#planner-people` input (`radius-sm`, padding 14px, globals.css:19) wrapped in an un-styled `<label>` (Planner.tsx:207–218). One form, two input geometries, two focus treatments (identical rings, different shapes), and a label with no `font-weight` while every other form's labels are 700–800. The pill-vs-square split is a genuine "two products" moment in the app's single most important form.

**Four vertical paddings across the app's text inputs:** 14px (planner), 12px (chat 12px/18px, settings select 12px/14px), 11px (inventory 11px/14px, comment-form 11px/14px, feedback, admin), 10px (`.stop-input input` globals.css:31). Nothing breaks, but the same "field" silently changes height by ~8px per page.

**Focus:** the global rule `input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 4px var(--lavender-soft)}` (globals.css:1, added as fix T2-4) plus a duplicate inside `.planner` (globals.css:19) means most inputs now share one focus language. Good — this closed the prior three-language gap. Two residual wrinkles: (a) the 4px ring is visually thick at 15px inputs (it reads as a fat lavender halo); (b) `:focus-visible{…border-radius:4px}` (globals.css:1) is a stray — it can square-off a focused pill in edge specificity cases, and it's semantically odd (outline follows border-radius anyway). Low impact.

**Checkboxes** use `accent-color:var(--accent)` (`.inline-check` globals.css:28, `.consent input` globals.css:34, roadtrip round-trip/inventory toggles) — a consistent, modern touch. No custom checkbox art, which is fine at this scale.

---

## 7. Iconography — Unicode glyphs and emoji; no icon library

**No icon library is installed** (package.json: zero icon/lucide/heroicons deps), and the app makes do with Unicode:

- **↑** send button — `Planner.tsx:199` and `PlanView.tsx:127`, 18px inside a 46px circle.
- **↻** swap/refresh place — `PlanView.tsx:128`, inside the 34px `.icon-action`.
- **×** remove stop — `roadtrip/page.tsx:56`, inside `.icon-action`.
- **→** "create plan" affordance on featured cards (`page.tsx:58`), and — more prominently — **the leg separator in roadtrip results**, `{from} → {to}`, hard-coded as U+2192 in `lib/roadtrip-translations.ts` across ~18 locales (lines 36, 82, …) and in the page fallback (roadtrip/page.tsx:56).
- **☁** weather in trip-facts (`PlanView.tsx:122`).
- **Emoji** ☕ 🍜 🏛️ as featured-card thumbs at 44px (`page.tsx:6–10`, rendered in `.featured-card .thumb` globals.css:16).

**Verdict: these are the weakest craft element in the component layer.** Three concrete problems:
1. **Weight/baseline variance**: U+2192 and U+21BB (↻) are geometric symbols that ignore `font-weight`; U+2601 (☁) and U+2191 (↑) sit on the text baseline, so inside a 46px circle the arrow renders visibly off-center (high or low) — the classic "Unicode icon looks misaligned" defect. `×` (U+00D7) is a math symbol, thinner than an X, and reads as text.
2. **Cross-platform rendering**: ☕ (U+2615, no VS16) can render as a monochrome text glyph on Windows while 🍜/🏛️ render as full-color emoji — the three thumbs will look like *different species* of icon depending on OS. (Ground truth captured on Edge/Win; user screenshots would show a flat coffee cup next to two color emoji.)
3. **Inconsistency in *role* of symbol**: the same ↑ is used for both "send chat" and "send prompt"; ↻ means both "swap this place" and (later) version history; the → does double duty as a button affordance and a list separator. A stroke-based icon set (lucide ~28KB) would fix alignment, weight, and semantics in one move. The `aria-label`s are all present and correct, so the swap is low-risk.

The FAQ "+" is CSS-drawn and rotates to × on open (`.faq-item summary::after`, globals.css:16) — a legitimately nice CSS-only touch; keep it.

---

## 8. Card hierarchy — one class, six paddings

`.card` base: `padding:24px`, `radius-lg`, `shadow-sm`, 1px `--line` (globals.css:10). Overridden paddings: **18px** in `.workspace .card` (globals.css:25), **28px** planner (globals.css:19), **26px** `.step` (globals.css:16), **36px** `.settings-page` (globals.css:34), **40px** `.login-card` (globals.css:34). The task's 24-vs-18 discrepancy is real and it means the *same* `.card` component renders at different internal density depending on which ancestor it sits in — the workspace cards are visibly tighter than a history/explore card. Dense workspace is defensible (three columns of 620px+ panels need room), but it should be a named variant (`.card-dense`) rather than a context override, otherwise future `.card` changes silently break the workspace.

Worse: `.offer-card` in explore relies entirely on `.card` for its chrome (only h2/secondary rules are its own, globals.css:28), and **the admin booking queue forgot the class**: `admin/page.tsx:569` renders `<article className="offer-card">` — no `card` — so the whole "Booking support queue" section (fields, notes, references) renders as raw text in a 3-col grid on paper background. This exact defect was flagged as **H1 in the prior audit** (`research/ui-aesthetics/03-components.md`) and is **still present**. It is the clearest example of the system's fragility: card chrome is inherited, not owned.

---

## Full categorized findings

### Blocker
- None at the "page breaks" level. The nearest thing is the admin booking section (below), which breaks a whole internal page section visually.

### High
- **H1. Admin booking queue renders as raw text** — `.offer-card` without `.card` at `admin/page.tsx:569` (cf. correct usage `explore/page.tsx:66`, `support/page.tsx:62`). Open section, no surface, no border, no padding. Still unfixed since prior audit H1.
- **H2. No button size scale; 4–5 fabricated heights.** ~53px base pill (globals.css:7), forced 46px in inventory/admin (globals.css:28,40), 43px mini `.retry-action` (globals.css:10), 49px `.comment-form .primary` (globals.css:25), and the 38px `.trip-actions .icon-action` rule (globals.css:25) that is dead CSS — the plan-page header actually shows nine ~53px `.secondary` pills. No named `btn-sm/md/lg`; sizes are one-off overrides.
- **H3. Unstyled native buttons on the support page** — `support/page.tsx:67` renders "Hủy" as a bare `<button>` (no class) four times, default UA chrome sitting next to styled `.secondary` pills. Visible defect on the page.
- **H4. `.primary{width:100%}` as a base default** (globals.css:7). Every context must override (roadtrip:31, cta-banner:16). This is the root cause class of H1 and will keep producing "full-width surprise" buttons.

### Medium
- **M1. Pill + square inputs coexist inside one form** — `.chat-box input` (999px) vs `#planner-people` (radius-sm) in the same planner card (globals.css:19,22; Planner.tsx:184–218); the people `<label>` is also the only un-styled label in the app.
- **M2. Input vertical padding fragmentation** — 10/11/12/14px across stop-input / inventory / comment / settings / admin / chat / planner.
- **M3. Radius governance** — Leaflet's 4px zoom controls / 3px tooltip / 5px attribution (leaflet.css defaults) sit unreconciled inside a 12–24px system (only popup is themed, globals.css:40); same-rank surfaces use 12/16/24px arbitrarily; pill radius applied to passive tags as well as CTAs flattens hierarchy.
- **M4. Three hover-lift amplitudes** — -1px (buttons, slot) vs -2px (timeline) vs -4px (featured-card) with no documented rule.
- **M5. Inconsistent press feedback** — circles have `:active scale(.94)`; pill trio + chips have none. And send-button disabled opacity is .5 in workspace vs .55 in planner (globals.css:22 vs 19).
- **M6. Unicode glyphs/emoji iconography** (see §7) — baseline misalignment in circular buttons, mixed text/color emoji, no icon library.
- **M7. Two tab dialects** — `.day-tabs` (borderless lavender fill, 8/14px) vs `.inventory-tabs` (bordered surface, 11/20px), same active color, different idle/hover languages (globals.css:25,28).
- **M8. Map markers hard-code palette-bypassing colors** — `#e4572e`/`#0f766e` in `MapView.tsx:37,49` and `RoadTripMap.tsx:15–16`, with no token route. (Color-lane territory, but it's component-internal craft.)
- **M9. Light-mode flatness** — `--shadow-sm` @ .05 alpha and `--line` @ ~3.5% contrast barely separate cards from paper; the app reads "flat" in light mode more from under-tuned borders/shadows than from design intent (ground-truth pixels 95% `#e0e0e0`).

### Low
- **L1. Dead CSS** — `.trip-actions .icon-action{height:38px}` (globals.css:25), `.planner textarea/select` (globals.css:19), `.bubble.typing` (globals.css:22) with its polished-but-unused typing animation, `.nav{border-radius:0 0 0 0}` (globals.css:4).
- **L2. Number-badge inconsistency** — 40px square-r12 (landing `.step::before`), 28px circle (`.stop-index`), 30px circle (`.stop-input>span`). Same concept, three forms.
- **L3. `:focus-visible{…border-radius:4px}`** (globals.css:1) is a stray that can square-off focused pills in edge cases.
- **L4. `.retry-action` / `.comment-form .primary`** are unnamed size variants that should be `.btn-sm`.
- **L5. Card padding via context override** — `.workspace .card{padding:18px}` and `.login-card{40px}`/`.settings-page{36px}` mutate the same `.card` instead of named variants.

### Note
- **N1. The 6px bubble tail** is a CSS shortcut vs a real SVG tail; acceptable, but it's the one component that looks "hand-rolled."
- **N2. Featured-card emoji thumbs** render text-style (☕) vs color-style (🍜🏛️) depending on OS/font — will look inconsistent on Windows.
- **N3. Ellipsis drift** — "Đang tải…" (U+2026) on support vs "Đang tải..." (3 dots) on admin.
- **N4. `.workspace-page{width:100vw}`** full-bleed hack causes the horizontal overflow in ground-truth #2 (layout lane's defect, but it visually clips the map panel's 4px zoom controls on the right edge).
- **N5. Login busy opacity** `style={{…,opacity:busy?.6:1}}` (`login/page.tsx:71`) is valid but cryptically formatted.
- **N6. High points to protect:** assistant-dot halo, slot-selected ring, chip aria-pressed, trip-facts dashed "stale" marker, FAQ CSS "+"→"×", reduced-motion handling, the lavender ring system.

---

## (1) Executive summary (~250 words)

The component layer of "Mình Đi Đâu Thế" has a genuine craft voice: a disciplined radius/shadow token set, one coherent `cubic-bezier(.4,0,.2,1)` motion family, and several micro-details that are genuinely good — the assistant-dot's 6px halo, the 4px lavender ring on selected slots, the dashed-border "stale data" pill, the mirror-symmetrical 6px chat tails, the CSS "+"→"×" FAQ rotation, and universal `prefers-reduced-motion` support. That voice, however, is enforced at the token layer only; the moment components consume those tokens, discipline collapses into improvisation. The same button ships at ~53px, 46px, 49px, and 43px depending on page; the same `.card` ships at 18, 24, 26, 28, 36, and 40px padding; inputs come in pill and square in the same form with four vertical paddings; there are three hover-lift amplitudes, two tab dialects, two disabled-opacities for one button, and press feedback that exists only on the round buttons. The most damning single fact: `.primary{width:100%}` baked into the base class already caused one whole admin section (booking queue) to lose its card chrome and render as raw text — still live today. Iconography is the weakest element: no icon library, Unicode arrows that sit off-center inside circles, and emoji thumbs that will render as mixed monochrome/color across OSes. Verdict: every component is individually competent and modern; collectively the app fragments into competing variants. **Score: 6.5/10.**

## (2) Top 5 findings

1. **Admin booking queue lost its `.card`** — raw-text section (admin/page.tsx:569); pre-existing, still unfixed.
2. **No button-size scale** — 4–5 heights fabricated via overrides; the plan header's compact 38px rule is dead CSS while nine 53px pills render instead (globals.css:25,7).
3. **`.primary{width:100%}` as base default** — a footgun that already produced the admin bug; every context opts out (globals.css:7).
4. **Iconography is Unicode/emoji** — baseline-misaligned ↑↻× in circles, → as a data separator in 18 locales, mixed monochrome/color emoji thumbs; no icon library (Planner.tsx:199, PlanView.tsx:128, page.tsx:6–10, roadtrip-translations.ts:36).
5. **Light-mode flatness from under-tuned separators** — 5% shadow-sm + ~3.5% card border make cards float on paper; the dark shadows seen in light screenshots are a CDP artifact, not code (globals.css:1,43).

## (3) Confidence: 8/10

Verified by direct code reading (every CSS token block, every button/input/bubble rule, all TSX render sites, leaflet.css defaults, translation files) and reconciled against the ground-truth rendered radii/shadow sets. The emulation caveat was resolved by first principles (dark shadow tokens exist only inside the `prefers-color-scheme:dark` block; no hardcoded shadows elsewhere), so the light-shadow verdict is high-confidence. Ground-truth tally: ~30 code-verified facts; ~4 judgments are design-taste (pill overuse, bubble-tail datedness, Unicode-icon cheapness) — sound but inherently subjective; 1 unresolved cross-lane item (workspace overflow, N4). Score docked for the unshippable-without-contest items (H1–H3) and the absence of any size/state governance.
