# Ground-truth visual data (captured from real rendered pages)

Collected via headless Edge 151 CDP + pixel analysis on 2026-08-08.
Pages rendered at 1440x1000 window, viewport ≈1399x873. Backend on :8000, frontend on :3000.
A real plan token was generated (mock AI mode). Both prefers-color-scheme light AND dark captured.

IMPORTANT: This analysis is about VISUAL BEAUTY ONLY, not functionality.

## Browser-rendered facts (ground truth)

1. FONT: body fontFamily = `Inter, "Fig Grotesk", system-ui, sans-serif` BUT `document.fonts` shows ZERO Inter faces loaded.
   -> ALL text renders in system fallback (Segoe UI on Windows). Inter/Fig Grotesk are declared but never loaded.
   "Times New Roman" appears only on <HEAD>/<SCRIPT>/<TITLE> elements (system), never on visible UI.

2. PLAN PAGE HAS HORIZONTAL OVERFLOW (visual defect):
   - `<main class="workspace-page">` bounding: L=-7 R=1407 W=1414 while viewport vw=1399.
   - Leaflet map SVG + 4 map tiles extend to R=1434.
   - scrollWidth=1407 > clientWidth=1399 -> horizontal scrollbar appears.
   - Cause: `.workspace-page{width:100vw; margin-left:calc(50% - 50vw)}` — 100vw includes scrollbar width (~8px), and vw > clientWidth.
   This is a regression from the recent full-bleed fix.

3. LANDING hero type scale (rendered font-sizes, light mode):
   13px×13, 14px×23, 15px×4, 16px×58, 17px×1, 18px×1, 19px×4, 20px×5, 44px×4, 46px×3, 88px×1
   Notice: no sizes between 20px and 44px (gap), 44 and 46 nearly duplicate (two competing headings), 88px hero.
   Landing page height: scrollHeight=3095 (long page, mostly above-fold whitespace).

4. PLAN type scale: 10,11,12,13,13.33,14,15,16,18,18.72,19,20,22,50.9 (14 steps, dense, no clear modular rhythm).

5. Vertical gap distribution LANDING: only 2 values {32px×1, 72px×1} — extremely sparse capture because most
   section spacing comes from padding, not gaps. PLAN: {32px×1}.

6. COLOR (light mode landing, computed styles on elements):
   - body bg = rgb(247,246,243) = #f7f6f3 (paper) ✓ light
   - BUT element backgrounds include DARK-mode colors: rgb(31,18,34)=#1f1222 (dark surface) ×10,
     rgb(42,24,46)=#2a182e ×5, rgb(205,179,255)=#cdb3ff ×3, rgb(20,16,20)=#141014 ×1, rgba(20,16,20,0.78) ×1,
     rgb(174,134,247)=#ae86f7 ×1, rgb(111,214,164)=#6fd6a4 (dark green) ×1, rgb(255,255,255) ×1.
   -> SUSPICIOUS: dark-mode color tokens appearing in light mode screenshots suggests some components
      hardcode dark palette or the CDP emulation partially applied. Needs code verification.

7. TEXT colors (light landing): #eae8ea ×20 (dark ink!), #cdb3ff ×14 (lavender), #a99fae ×13 (dark muted),
   #ae86f7 ×9, #2a182e ×3, #948b96 ×3, #000 ×2, #fff ×1, rgba(255,255,255,0.85) ×1.
   -> Most visible text colors are the DARK-mode tokens. Combined with #6 body bg being light,
      suggests the CDP emulation set prefers-color-scheme=dark for computed styles while body
      stayed light?? MIXED. MUST verify which render users actually see.

8. Pixel analysis (actual screenshots, light mode):
   - landing-light.png: 95.2% bright, mean_sat 0.036, top colors #e0e0e0 (94.6%), #200020 (2.8%), #808080.
     => LIGHT mode = very pale, low saturation, mostly whitespace. Almost colorless.
   - explore-light.png: 96% bright, mean_sat 0.030, 95.7% #e0e0e0. Nearly empty white page.
   - settings-light.png: 94.3% bright, mean_sat 0.036.
   - history-light.png: 62% bright, 37% dark (#200020) — big dark block at bottom = empty-state illustration/icon?
   - roadtrip-light.png: 66.5% bright, 31% dark.
   - login-light.png: 72.5% bright, 25% dark.
   - plan-light.png: 90.4% bright, mean_sat 0.053, 80% #e0e0e0 — has map area with muted colors.
   => OVERALL: light theme is extremely low-color. The lavender palette appears only in a few spots.

9. Dark mode screenshots (prefers-color-scheme dark):
   - landing-dark.png: 94.9% dark, top #000000 73%, #000020 12%, #200020 6%, #e0e0e0 1.9%, #c0a0e0 1.0%.
   - plan-dark.png: 66% dark, 22% bright; #000000 34%, #000020 26%, #e0e0e0 8.5%, #c0c0c0 5.1% + map blues.
   => dark mode: page bg #141014 quantizes to pure black; lavender shows as #c0a0e0.

10. Shadows (light, computed): box-shadow values are `rgba(0,0,0,0.4) 0 1px 2px` (DARK-mode shadows!),
    `rgba(0,0,0,0.45) 0 2px 8px` (dark), `rgba(0,0,0,0.6) 0 32px 80px` (dark xl), plus ring shadows
    rgb(53,36,56) 0 0 0 4/6px (dark line). Light shadows should be rgba(42,24,46,0.05–0.16).
    -> computed styles captured are DARK tokens. Yet screenshots pixels are LIGHT.

## Key conclusion on the emulation caveat

- `Emulation.setEmulatedMedia prefers-color-scheme: light` produced LIGHT pixels (screenshots #6 body light)
  but getComputedStyle at evaluate-time returned DARK token values. Interpretation ambiguity.
  -> The source of truth for light theme must be re-verified by code analysis (globals.css tokens) rather than
     computed styles, while PIXEL screenshots are trustworthy for what users see.
  -> Dark pixels in light screenshots (explore 96% white with few dark glyphs) = near-empty pages.

## Data files produced
- visual_light_landing.json / visual_light_plan.json / visual_light_explore.json / visual_light_roadtrip.json / visual_light_login.json
- screenshots in C:\Users\Admin\AppData\Local\Temp\opencode\shots\ (*-light.png, *-dark.png)
- layout metrics: landing dom=139 text=1658px... plan dom=252 text=4377 scroll=1407x1496.
- explore dom=80 text=574 (almost empty) — explore page likely renders empty search UI only.
