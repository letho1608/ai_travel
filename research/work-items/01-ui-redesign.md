# Lane 1 — UI Redesign ("Sửa lại giao diện"): State of the Frontend UI

**Agent lane:** UI redesign — what's broken, what needs fixing, what a good redesign looks like.
**Scope:** frontend only. Read files as of commit `b8b782e` (current `main`, working tree has research-doc deletions only).
**Method:** full read of `globals.css` (expanded from minified long lines), `PlanView.tsx`, `Planner.tsx`, `page.tsx`, `history/page.tsx`, `Navigation.tsx`, `Footer.tsx`, `MapView.tsx`, `LayoutProvider`, all 12 routes spot-checked, `i18n-core.ts`, `api.ts`, `next.config.mjs`.
**Lane boundaries:** itinerary *generation logic*, *data/images freshness*, *external-platform navigation*, *manual place-change feature*, and *visit-duration display* are owned by lanes 2–6. Where a UI defect overlaps (e.g., change-menu dialog semantics), I flag the UI layer only.

---

## 0. Overall verdict

The UI is in **decent shape and needs polish, not a rebuild**. The green retheme landed as a set of *cascade overrides* rather than a clean token rewrite (globals.css:73), which leaves dead tokens, a few lavender-gray stragglers, and — more importantly — a set of **hard-coded colors in the itinerary card that break in dark mode**. The biggest "looks unprofessional" items in a demo are not layout, they are:

1. Vietnamese text leaking into **all 18 non-Vietnamese locales** (`LocaleProvider.tsx:76–93`) — visible on the landing page footnote and the retry button.
2. Dark-mode contrast failures on the most prominent action area of the app (the itinerary summary "Lưu/Chia sẻ/Tạo lại" buttons).
3. The history screen (a primary demo surface) is entirely hard-coded Vietnamese and uses `vi-VN` date/cost formatters — it silently ignores the 19-locale system.
4. Modal-dialog semantics (change/delete popups) announce `role="dialog"` but do not trap focus or add a scrim.
5. Mobile touch targets below 44px on the primary slot action row.

Everything below is categorized by severity (Blocker / High / Medium / Low / Note) with `file:line` refs.

---

## 1. Design tokens & the green retheme — assessment

### 1.1 Token system map
`globals.css:1` defines a coherent token set: `--ink`/`--ink-2`/`--ink-3` text scale, `--muted`/`--muted-2` secondary text, `--paper`/`--surface`/`--surface-2` surfaces, `--brand`/`--brand-hover`/`--brand-contrast`/`--accent`/`--accent-2`, `--lavender`/`--lavender-soft`/`--lavender-50` (now green pastels despite the name), `--green`/`--green-soft`, `--sun`/`--sun-soft`, `--danger`, `--info`, `--line`/`--line-2`, shadow/radius/container/font/easing tokens. Dark mode re-declares every color in `@media(prefers-color-scheme:dark)` (globals.css:639). Reduced-motion is respected (globals.css:17). This is a *solid* base.

### 1.2 Retheme was applied as overrides, leaving dead tokens
`git show 8e3f456` confirms the retheme added a second `:root` block at **globals.css:73** (`--brand:#086b27; --brand-hover:#075a22; --accent-2:#086b27; --muted-2:#596b59`) plus a dark-mode block, rather than rewriting line 1. Consequences:

- **Dead base values** at globals.css:1: `--brand:#063b1b`, `--brand-hover:#123f24`, `--accent-2:#5fa858`, `--muted-2:#8ea18c` are unconditionally overridden later. Any future edit at line 1 silently won't apply. **[Low]**
- **Leftover lavender-gray tones in live tokens** (not overridden anywhere): `--muted:#6f6570` and `--line:#e0dde0` at globals.css:1 are gray-with-purple-hue (R≈G, B slightly higher), a visual hangover from the purple theme. They are used for the *entire* secondary-text scale (`.lead`, `.nav-links a`, `.history-card>p`, `.trip-header p`, `.slot p`) and every card/input border. Next to the warm green brand these read as "dusty mauve." A taste-level retheme completion item: recast `--muted` and `--line` to neutral green-tinted grays (e.g. `#5c6b5f` / `#dde6dc`). **[Medium — taste, not bug]**
- The token name `--lavender*` is now green-pastel content. Harmless but confusing for maintainers. **[Note]**

### 1.3 Dark mode — the real gap
The dark block (globals.css:639–706) overrides most components, but **several itinerary-specific selectors defined *after* line 639 in the file are hard-coded light-theme colors with no dark override**:

- `.itinerary-summary-actions .secondary` at globals.css:581 — `background:#f3f2ee; color:#111; border-color:#d8d5cd`. In dark mode this renders a **light-gray pill** on a dark card — the single most visible inconsistency in the whole app. **[High]**
- `.itinerary-regenerate` at globals.css:358 — `color:#086b27!important` on `background:var(--green-soft)!important`. In dark mode `--green-soft` = `#173528`, so the label is **dark-green-on-dark-green**; computed contrast ≈ **2.0:1** (fails WCAG AA, roughly 4× below the 4.5:1 target). This is the app's big "Tạo lại" button. **[High]**
- `.itinerary-summary-actions .primary` (globals.css:578) — `#086b27` bg / `#fff` text; legible in dark (≈5.5:1) but a "dark blob" next to dark surfaces. **[Low]**
- `.result-ready` (globals.css:620) — `border-color:#d8ded5` stays a pale frame on dark card. Cosmetic. **[Low]**
- `.history-create` (globals.css:396), `.history-filters button[aria-pressed=true]` (globals.css:403), `.history-card footer a` (globals.css:416), `.itinerary-summary-badge` (globals.css:353), `.action-toast` (globals.css:81–83) all hard-code `#086b27`/`#075a22`/`#9f2f20` and are untouched by the dark block. All remain legible (white/off-white text on them), so they are **consistency debt, not failures**. **[Low]**
- `.itinerary-card-hero` gradient `#d8e9d0 → #9bc7ac → #f2c99f` (globals.css:366) is not tokenized and stays pastel-bright in dark mode. Taste item. **[Note]**

### 1.4 Focus-visible system
Global `:focus-visible` outline (globals.css:7) exists for all non-input controls. Inputs get `outline:none` + a 4px `--lavender-soft` ring (globals.css:8, also per-component at 148, 177, 280, 333, etc.). The system is **consistent** and green-themed. Gaps:
- No `:focus-visible` fallback where buttons are styled via `border` only (`.chip`, `.day-tabs button`, `.history-filters button`) — the global outline covers these, so acceptable. **[Note]**
- `.history-plan-nav>a:focus-visible` (globals.css:448) styles background only; fine. **[Note]**
- Leaflet map controls and popup close buttons keep browser defaults (Leaflet ships its own focus styles). **[Note]**

---

## 2. Landing page + chat (app/page.tsx, Planner.tsx)

### 2.1 Landing (`app/page.tsx`)
- Hero grid + `.planner` card are healthy; `hero` collapses to one column at ≤900px (globals.css:102). **[OK]**
- `featured-card` is an `<a href="/">` whose `onClick` `preventDefault()`s and focuses `#planner-context` (page.tsx:54). It is **not** a card that writes a suggested context — it only focuses the input. In a demo this looks like a broken link ("click a card, nothing happens except a cursor move"). Suggest either prefilling the idea or removing the `href`. **[Medium — interaction clarity]**
- The section `aria-labelledby` pattern is correct. `cta-banner` reuses `t("heroLead")` for its copy (page.tsx:102) — duplicates the hero paragraph verbatim below. **[Low]**

### 2.2 Planner chat (`components/Planner.tsx`)
- Good a11y groundwork: `role="log" aria-live="polite"` on transcript (line 246), `role="status"` for status (325), `role="alert"` for errors (330), `aria-pressed` on idea chips (277), `aria-label` on the send button (308).
- The duration follow-up ("Thời lượng…" prompt + chips) works and is inline — no modal, so no focus-trap complexity. Chip grid on mobile: `flex:1 1 calc(50% - 7px)` (globals.css:159). **[OK]**
- The `.planner` card uses `overflow:hidden` (globals.css:145) for its top gradient strip. The transcript is a separate scroll region (`max-height:300px`, 360px mobile, globals.css:155–158), so content is never clipped by the card. **[OK]**
- **Taste/item:** the send button is a bare `↑` character (Planner.tsx:309) in a 46px circle — fine, but on some devices the glyph baseline sits low. **[Note]**
- **UX defect:** after an error, `retryGenerate` (Planner.tsx:233–237) replays `lastRequest` but the input stays empty and `context` is `""`; there is no way to *edit* a failed request without clicking an idea chip first. Minor, but mildly confusing in demo. **[Low]**
- **i18n defect (also §7):** the footer `dataNotice` and the retry label render Vietnamese in every non-Vietnamese locale because `LocaleProvider.tsx:76–93` pastes the `vi` strings for `retryCreate:"Thu lai"` and `dataNotice:"Du lieu dia diem dung catalog…"` into all 18 other locale blocks. This is visible on the landing page in any non-Vietnamese demo. **[High]**

---

## 3. Itinerary workspace (components/PlanView.tsx + globals.css)

This is the demo centerpiece; the code is mature (versioned actions, AbortController cleanup, stale-token guards at lines 113–131, 136–141). UI findings:

### 3.1 "Trở lại chat" / ready header
- `.result-back-to-chat` (PlanView.tsx:226) navigates with `window.location.assign("/")` (line 221). Full reload — acceptable for MVP; a `Link`/`router.back()` would be smoother. **[Low]**
- "AI đã tạo xong" header (`.result-ready`, line 227) has `aria-labelledby` pointing at a real `<h2>`. **[OK]**
- Dark-mode: `.result-ready-badge` resolves to `--green` (`#6fd6a4`) on `--green-soft` (`#173528`) → good contrast in dark. **[OK]**

### 3.2 Slot cards
- Grid `28px 56px 1fr auto` (globals.css:203); time column renders `bat_dau<br/>ket_thuc`; place details in col 3; actions on a full-width second row (`.slot-actions`, globals.css:587). Layout is stable, no overlap. **[OK]**
- **Slot-level a11y pattern is unusual:** a full-card transparent `<button class="slot-select">` covers the whole card (`position:absolute; inset:0`, globals.css:212) with `aria-pressed` + `aria-label={place name}` (PlanView.tsx:235). Inner interactive elements (change/delete buttons, source link) are *siblings* of the overlay, re-enabled via `pointer-events:auto` (globals.css:209, 586). This works, but the overlay means **keyboard focus lands on a full-card-size button first**, then the change/delete buttons — a keyboard user must Tab through a giant invisible button to reach actions. Acceptable; a `<button>` that announces the whole card is arguably a useful landmark. **[Low]**
- **Touch targets:** `.icon-action` is `34×34` (globals.css:54) and `.change-place` `min-height:34px` (globals.css:588) — both **below the 44px mobile guideline** on the primary slot action row. `.delete-menu button` `min-height:38px` (globals.css:596). **[Medium — WCAG 2.5.5 / mobile HIG]**
- The `.source` link is `font-size:11px` (globals.css:210) — below the practical 12px minimum and a small tap target. **[Low]**
- Mobile rules `.itinerary-panel .icon-action{grid-column:3}` / `.slot-photo~.icon-action{grid-row:3}` (globals.css:264–265) are **dead** — actions now live inside `.slot-actions` (full-width row) since the action row refactor, so the old 3-column mobile layout rules never apply. Not harmful; dead CSS. **[Note]**

### 3.3 Summary actions (Lưu / Chia sẻ / Tạo lại)
- The Save button icon is a 21px `background-image` on a `font-size:0` span (globals.css:577–583); the bookmark/share glyphs are inline data-URI SVGs. Light-mode fine.
- **The dark-mode defects from §1.3 live here** (`.itinerary-summary-actions .secondary` light-gray pill at globals.css:581; `.itinerary-regenerate` unreadable label at globals.css:358). **[High — see §1.3]**
- The icon spans have `aria-hidden="true"` and the buttons carry real text labels — good. **[OK]**

### 3.4 Change / delete popups (the change/delete feature UI)
Both are rendered via `createPortal` to `document.body` (PlanView.tsx:271, 273–338), so the earlier clipping fix works; they escape `overflow:hidden` ancestors.

- **Delete menu:** `role="dialog" aria-modal="true"` + `aria-label` (line 271), `autoFocus` on Cancel, Escape + outside-mousedown dismiss (line 131), trigger refocus via `requestAnimationFrame` in `closeDelete` (line 115), and a positioning `useLayoutEffect` that flips above/below and keeps it on-screen (line 130). **This is well done.** Gaps: no focus trap (Tab can escape an `aria-modal` dialog), no `aria-labelledby`/`aria-describedby` tying the confirm copy to the dialog, and a one-frame flash at `left:16,top:16` before layout runs. **[Medium — modal semantics]**
- **Change menu:** `role="dialog"` but **no `aria-modal`**, no scrim/backdrop, `z-index:1000` (below delete menu's 1010 — a delete trigger inside an open change menu would render on top, though state is mutually exclusive so it's theoretical). Focus is moved to the first `.change-choice` on open (line 129) and returned to trigger on close (line 116). Escape works (line 129). No focus trap. The replacement-search input is `autoFocus` and gets a combobox with `aria-controls`/`aria-expanded` (lines 310–312) — nice.
- **Missing overlay/scrim** for both dialogs: content behind remains fully interactive. For an MVP this is acceptable; for "professional" polish, add a scrim + focus trap. **[Medium]**
- `.change-menu,.delete-menu{background:var(--green-soft)}` (globals.css:612) — in light mode the menus are *pale-green panels* (the whole dialog is tinted green, not just accents). Taste call; it reads intentional after commit "match change icon and popup color". **[Note]**
- **Delete positioning with `useLayoutEffect`** repositions on `scroll` (capture) and `resize` (line 130) — good robustness. **[OK]**

### 3.5 Toast & busy
`.action-toast` (globals.css:81) is fixed, safe-area aware, `role="status" aria-live="polite" aria-atomic="true"` (PlanView.tsx:230), auto-dismisses after 5s (line 128). Busy indicator is a `role="status"` spinner+label. Good. **[OK]**

### 3.6 Map panel
`MapView.tsx` (in lane 1's scope only for *UI*):
- Marker/polyline colors are hard-coded `#086b27` / `#bb4d45` (MapView.tsx:37, 49) rather than tokens — consistent with brand, fine for MVP. **[Note]**
- `fitBounds(points, {padding})` runs on **every** `selectedId` change (MapView.tsx:52, effect deps `[slots, selectedId]`). Selecting a slot re-fits the camera, defeating any manual pan/zoom the user did. Genuinely annoying in a demo. **[Medium]**
- Popup HTML is built by string interpolation (`slot.ten_dia_diem`, `slot.anh` — MapView.tsx:42). Place names come from the backend inventory, so risk is low; but names are not HTML-escaped. **[Low/Note — security-hygiene]**
- The `.map` div carries a hard-coded Vietnamese `aria-label` (MapView.tsx:58); Leaflet itself is not keyboard-operable (known limitation). **[Low]**

---

## 4. History screen (app/history/page.tsx)

### 4.1 The biggest i18n hole
Nearly every visible string is hard-coded Vietnamese: sidebar headings, "Tạo kế hoạch mới", filters "Tất cả/Gần đây/Dự định", badges "Dự định/Đã lưu", "Xem chi tiết", "Không có kế hoạch phù hợp…", the empty-state copy, and `formatDate`/`formatCost` hard-code `"vi-VN"` (history/page.tsx:33–37). Meanwhile the base keys for these strings (`historyTitle`, `notifications`, `markRead`, `noTrips`, `loadFailed`, …) exist in `baseTranslationKeys` (i18n-core.ts:5) — so the translation infra is *there*, the page just doesn't use it. The base layer of the screen (nav labels, notifications, messages) *does* use `t()`. **[High — demo in any non-Vietnamese locale]**
- Worse, **the filter/badge logic depends on Vietnamese**: `HistoryFilter` ids `all/recent/upcoming` are internal, fine, but the *labels* are hard-coded. Not a logic bug, but the screen is effectively Vietnamese-only despite the app's language switcher. **[High]**
- Layout: sidebar 310px sticky (`top:92px`, globals.css:387), collapses to horizontal scroll rail ≤720px (globals.css:432–442), grid 2→1 cols ≤1000px. Prior overflow fixes (`.history-plan-nav` ellipsis rules, globals.css:445–457) are in place and correct. **[OK]**
- `.history-grid` inside a `.history-page{max-width:1460px}` that is nested in the layout's `.shell{max-width:1200px}` (layout.tsx:12) — see §8. **[Note]**

---

## 5. Navigation, footer, and global chrome

- **Nav** (Navigation.tsx): brand + 4 links + admin (if authed) + CTA; active state, focus styles OK. At ≤760px it wraps to multiple rows (globals.css:36–40) instead of a drawer — fine for 5 items. `aria-label="Main"` is English; minor. **[OK]**
- **Footer** (Footer.tsx): `t()` used for most, but **"Support" (line 26) is hard-coded English and "Điều khoản" / "Bảo mật" (lines 30–31) are hard-coded Vietnamese** in a footer that is otherwise localized. In a non-Vietnamese demo, the footer mixes languages visibly. **[Medium]**
- Footer dark mode: `.site-footer{background:var(--surface-2)}` = `#063b1b` (very dark green) with `--lavender` links — good. **[OK]**
- **Missing global meta:** no `<meta name="theme-color">`, no favicon/PWA icons in `layout.tsx`, no `viewport` `viewport-fit=cover` meta (safe-area is handled in CSS for toast only). `next/font` Inter with `subsets:["latin","vietnamese"]` (layout.tsx:9) — good, but note it does **not** load Arabic/Hebrew/CJK subsets, so the 19-locale promise relies on system fonts for `ar/he/zh/ja/ko/th`. Acceptable, flag as Note. **[Note]**

---

## 6. Remaining routes (spot-check)

- **Explore** (`app/explore/page.tsx`): fully localized via `t()`; tabs use WAI-ARIA `role="tablist"/"tab"`/`aria-selected` but **no arrow-key roving focus** and no `tabpanel` association — partial tab semantics. **[Low]**
- **Roadtrip** (`app/roadtrip/page.tsx`): fully localized; the stop-editor grid collapses sanely ≤800px (globals.css:314–319). `.icon-action` (remove-stop) again 34px. **[Low]**
- **Settings** (`app/settings/page.tsx`): localized; delete-account confirm string is `"XOA TAI KHOAN"` (line 37) — a Vietnamese phrase required in all 19 locales (the translations explain it, but it's a hard-coded gate). The `<select>` for language is where users *choose* Arabic/Hebrew → see §7 RTL. **[Low]**
- **Login** (`app/login/page.tsx`): localized; Google button uses `locale` for the button locale (line 58); good `role="status"/"alert"` usage. **[OK]**
- **Support** (`app/support/page.tsx`): fully hard-coded Vietnamese; uses blocking browser `prompt()` dialogs for assignee/notes/provider reference (lines 41–44) — not mobile-friendly and visually jarring; the "Hủy" button has **no className** (line 67) so it renders as a raw browser button in a card grid. Internal-ops page → low priority, but it's a visible inconsistency if demoed. **[Low]**
- **Admin** (`app/admin/page.tsx`, 604 lines): hard-coded Vietnamese labels (STATUS_LABELS, lines 63–66) mixed with English UI text (e.g., `<a>Open</a>` at line 529). Internal tool → **[Note]**.
- **Terms / Privacy** (`app/terms/page.tsx`, `app/privacy/page.tsx`): static Vietnamese server components with versioned eyebrows — acceptable for an MVP demo in Vietnamese; not localized. **[Note]**

---

## 7. i18n / RTL assessment (the 19-locale system)

- **Architecture:** `LocaleProvider` (LocaleProvider.tsx:99–110) reads `travel_preferences.ngon_ngu` from localStorage, normalizes, sets `document.documentElement.lang` **and** `dir` for `ar`/`he` (line 101). Good baseline.
- **Flash of wrong language/dir:** `layout.tsx:12` hard-codes `<html lang="vi">` and the effect runs client-side — first paint for an Arabic/Hebrew/English user is Vietnamese-LTR, then flips. For `ar`/`he` this is an RTL visual flash. **[Medium]**
- **RTL is partial-but-mostly-OK:** the CSS is ~95% symmetric (padding, radii, grid gaps), and the few directional spots already use logical properties — `.action-toast{inset-inline-end…}` (globals.css:81), `.change-menu-close{inset-inline-end…}` (615), `.itinerary-summary-badge` via `inset-inline-start` (460). Remaining physical-LTR quirks: `.nav-admin{margin-left:8px}` (35), `.history-card footer a span{margin-left:5px}` (417), `text-align:left` on `.change-choice`/`.history-plan-nav button` (598, 392), `.brand::before`/`.footer-brand::before` diamond at physical left, and the back-arrow SVG in `.result-back-to-chat` (PlanView.tsx:226) pointing left (should mirror in RTL). None break layout; all are cosmetic in RTL. **[Low]**
- **Translation leakage (the standout):** the Vietnamese strings for `dataNotice` and `retryCreate` were copy-pasted into **all 18 non-Vietnamese locale blocks** (verified 18 occurrences of each; LocaleProvider.tsx:76–93). The landing-page disclaimer and the planner retry button therefore render Vietnamese in English/Japanese/Arabic/etc. This is the single most visible "unpolished" defect in a multi-locale demo. **[High]**
- **Latin/Greek/Cyrillic spacing:** long labels ("Tiếp tục xử lý", German compounds) wrap fine at 14px. **[OK]**
- **`getTranslation` fallback** (LocaleProvider.tsx:95) ends with `roadtripTranslations[locale][key]` without a `key in` guard; if a key is ever missing from a locale, `interpolate(undefined)` throws. Typed keys make this latent, but a belt-and-suspenders `?? key` fallback would be safer. **[Note]**
- **Backend error strings leak Vietnamese to UI:** `lib/api.ts:32,42,69,83` produce Vietnamese error messages surfaced verbatim (e.g., "Máy chủ không trả kế hoạch") in Planner's `errorDetail`. **[Low]**

---

## 8. Responsive / overflow / layout audit

- **`.shell` caps everything at 1200px:** the layout wraps *every* route in `<div className="shell">` (layout.tsx:12), so `.workspace-page{max-width:1500px}` (globals.css:186) and `.history-page{max-width:1460px}` (globals.css:384) are **dead constraints** — both pages render at 1200px max. The 3-column workspace still fits (min 240+360+340 + gaps ≈ 972px ≤ 1160 usable), so it's not a visible break, but it means the design intent for a wider workspace is unrealized and the map/timeline panels are tighter than designed. **[Medium — structural]**
- **Workspace reflow:** ≤1100px → `320px 1fr` with map dropping to a full row (globals.css:248–252); ≤760px → vertical stack ordered itinerary→map→chat (globals.css:253–268). Sensible mobile-first order (plan first, then map, then chat at the bottom). **[OK]**
- **Double horizontal padding** on workspace/history pages: 24px shell + 20px page = 44px gutter on desktop. Not broken, slightly wasteful. **[Note]**
- `.day-tabs` `overflow:auto` + `white-space:nowrap` (globals.css:198) — horizontal scroll on many days; fine, but no visible scroll affordance. **[Note]**
- Timeline `max-height:640px` inner scroll on desktop, `max-height:none` ≤760px (globals.css:371, 378). Good.
- Nav wraps on mobile (multiple rows) — can occupy 3 rows of sticky space on 360px screens. Acceptable for 5 links. **[Note]**
- `map-panel .map` min-height 520→400px mobile (globals.css:221, 259). Good.

**Mobile touch-target summary:** 34px `.icon-action`, 34px `.change-place`, 38px delete-menu buttons, ~34px `.history-filters` buttons, 44px `.chat-box` send button (ok), 52px primary buttons (ok). The slot action row is the weak spot. **[Medium]**

---

## 9. Severity-flagged findings (consolidated)

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| 1 | **High** | 18 non-Vietnamese locales render Vietnamese `dataNotice` + `retryCreate:"Thu lai"` | LocaleProvider.tsx:76–93 |
| 2 | **High** | Dark mode: itinerary summary Share button is a light-gray pill; Regenerate label ≈2.0:1 contrast on dark | globals.css:358, 578–583 |
| 3 | **High** | History screen hard-coded Vietnamese, `vi-VN` formatters; ignores locale system | history/page.tsx:33–37, 105–113 |
| 4 | **Medium** | Change/delete dialogs: `role="dialog"` without focus trap or scrim (delete is `aria-modal` but escapable) | PlanView.tsx:271–338, globals.css:592–596 |
| 5 | **Medium** | Map refits bounds on every selection, discarding user pan/zoom | MapView.tsx:52 |
| 6 | **Medium** | Touch targets 34px (`.icon-action`, `.change-place`) below 44px mobile guideline | globals.css:54, 588 |
| 7 | **Medium** | RTL/`lang` flash: `layout.tsx` hard-codes `<html lang="vi">`; effect flips dir client-side | layout.tsx:12, LocaleProvider.tsx:100–104 |
| 8 | **Medium** | `.shell` (1200px) caps workspace/history (designed 1500/1460px) — dead max-widths | layout.tsx:12; globals.css:186, 384 |
| 9 | **Medium** | Featured idea-cards navigate to `/` with preventDefault, only focus the input — looks broken | page.tsx:54 |
| 10 | **Medium** | Footer mixes hard-coded "Support"/"Điều khoản"/"Bảo mật" with localized links | Footer.tsx:26, 30–31 |
| 11 | **Low** | Dead base tokens from retheme-by-override (`--brand`, `--accent-2`, `--muted-2`) | globals.css:1 vs 73 |
| 12 | **Low** | Lavender-gray `--muted:#6f6570` / `--line:#e0dde0` remain (taste) | globals.css:1 |
| 13 | **Low** | Hard-coded hex greens scattered (`.history-create`, filters, summary actions, badge) — not tokenized | globals.css:353, 396, 403, 578–583 |
| 14 | **Low** | Popup HTML string interpolation not escaped (place names/URLs) | MapView.tsx:42 |
| 15 | **Low** | Explore tabs lack arrow-key roving + tabpanel wiring | explore/page.tsx:60 |
| 16 | **Low** | `errorDetail` surfaces Vietnamese backend errors in any locale | api.ts:32,42,69,83; Planner.tsx:168–172 |
| 17 | **Low** | Support page: raw `prompt()` dialogs + unstyled "Hủy" button | support/page.tsx:41–44, 67 |
| 18 | **Note** | `retryGenerate` replays last request; input left empty/uneditable | Planner.tsx:233–237 |
| 19 | **Note** | Dead mobile CSS for slot action columns | globals.css:264–265 |
| 20 | **Note** | `--lavender*` token names now hold green pastels | globals.css:1, 639 |
| 21 | **Note** | No `theme-color`/icons/`viewport-fit=cover`; Inter lacks ar/he/CJK subsets | layout.tsx:9–12 |
| 22 | **Note** | `getTranslation` last-resort access can return undefined → throw | LocaleProvider.tsx:95 |
| 23 | **Note** | `result-back-to-chat` uses full-page `location.assign` | PlanView.tsx:221 |

---

## 10. Prioritized UI-fix plan (sized for an MVP demo)

Distinguish **hard defects** (fix first) from **taste** (optional). No rebrand — everything is compatible with the current Hanoi-green identity.

### Tier 0 — Demo-blockers (a day or less)
1. **Kill the Vietnamese leakage** in `LocaleProvider` for `dataNotice` + `retryCreate` across the 18 non-`vi` locales (find+replace once; the keys are identical per block). *Defect.*
2. **Dark-mode repair on the itinerary action area:** tokenize `.itinerary-summary-actions .secondary` and `.itinerary-regenerate` (drop `!important`, map to `--surface-2`/`--green`/`--ink` so the dark block inherits), add dark overrides for the hard-coded greens. *Defect.*
3. **Make history localized** for at least `vi`+`en`: swap hard-coded labels to the existing base keys, and pass `locale` into `Intl.DateTimeFormat`/`NumberFormat`. *Defect.*

### Tier 1 — Professional-polish (1–2 days)
4. Add a **focus trap + scrim** for the two `role="dialog"` menus (a 20-line `useEffect` trap; scrim via an existing token like `rgba(6,59,27,.4)`). *Defect.*
5. **Don't `fitBounds` on selection** — only on `slots` change (move `selectedId` out of the effect deps or compare). *Defect.*
6. Bump slot-action touch targets to ≥44px (`.icon-action`, `.change-place`, delete-menu buttons). *Defect (WCAG 2.5.5).*
7. Set `<html lang>`/`dir` server-side or early (small `headers()`/middleware or inline script) to kill the RTL flash. *Defect.*
8. Recast `--muted` and `--line` to neutral green-gray (one-line token change; verify against the whole page). *Taste, high payoff.*

### Tier 2 — Consistency (worth doing before a serious demo)
9. Footer hard-coded strings → `t()`; add `support/terms/privacy` keys. *Defect.*
10. Featured idea-cards: make click actually prefill the planner (or drop the `<a>` and use a real button). *Defect.*
11. Consolidate hard-coded `#086b27`/`#075a22` to `var(--brand)`/`var(--brand-hover)` (mechanical replace, ~8 spots). *Taste/debt.*
12. Delete dead `.shell`-capped max-widths or widen the layout for the workspace; add `aria-pressed` to day-tabs. *Taste.*
13. Escape popup strings in `MapView` popup HTML. *Defect (hygiene).*

### Tier 3 — Nice-to-have (only after the above)
14. Explore tab arrow-key nav; Planner retry-edit affordance; theme-color/icons; mirror back-arrow in RTL; `.nav-admin` logical margins; admin/support language cleanup.

---

## 11. Top 5 most concerning findings

1. **Vietnamese leaks into all 18 non-Vietnamese locales** (`LocaleProvider.tsx:76–93`) — visible on the landing page in any English/other-language demo; instantly reads "broken."
2. **Dark-mode illegibility of the primary action buttons** — the regenerate label at ≈2.0:1 contrast and a light-gray Share pill on a dark card (globals.css:358, 581).
3. **History screen ignores the locale system** entirely despite being a primary demo surface (`history/page.tsx:105–113`).
4. **Dialog semantics without focus trapping** on the change/delete menus — screen-reader users get `role="dialog"`/`aria-modal` with no containment (`PlanView.tsx:271, 273–338`).
5. **Map camera fights the user** — every slot selection resets bounds (`MapView.tsx:52`).

---

## 12. Confidence & ground truth

**Confidence: 7/10.**

**Ground-truth tally (load-bearing conclusions verified by reading actual code):**
- Token map, retheme-by-override (`:root` block at globals.css:73), dead base values, `--muted`/`--line` lavender-gray — **verified** by reading globals.css:1–73 and `git show 8e3f456`.
- Dark-mode contrast failure of `.itinerary-regenerate` (#086b27 on #173528) — **verified** values from globals.css:358 + dark block:639; contrast ≈2.0:1 is my *computed* math (not run through a tool) — call that judgment, but the values are read from source.
- 18-locale Vietnamese leakage for `dataNotice`/`retryCreate` — **verified** by 18 exact string occurrences (LocaleProvider.tsx:76–93).
- History page hard-coded Vietnamese + `vi-VN` formatters — **verified** (history/page.tsx:33–37, 105–113).
- RTL `dir` logic, layout.tsx `lang="vi"` — **verified**.
- `fitBounds` on `selectedId`, popup interpolation, touch-target sizes, portal/dialog semantics — **verified** from source.

**Model-judgment (unverifiable locally, marked):** actual WCAG contrast ratios computed by hand; subjective "reads as mauve/dusty" for `--muted`/`--line`; severity weighting of "demo polish" vs. "bug"; assertion that no CSS selector elsewhere repairs the itinerary-action dark-mode styles (I grepped the full dark block and the file for these selectors — found none, so this is near-verified). Any numerical contrast claim should be re-run with a contrast tool before acting.
