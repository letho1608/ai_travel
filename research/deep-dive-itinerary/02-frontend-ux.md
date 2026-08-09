# Deep-Dive Audit — Lane 2: Frontend UX / UI Quality / Input Experience

**Product:** Mình Đi Đâu Thế (Vietnamese AI day-trip planner)
**Repo:** `D:\Code\aithucchien\ai_travel` · frontend in `frontend/`, backend in `backend/`
**Date:** 2026-08-07
**Scope (this lane):** `frontend/components/Planner.tsx`, `PlanView.tsx`, `MapView.tsx`, `LocaleProvider.tsx`, `app/globals.css`, `app/layout.tsx`, `app/page.tsx`, `app/plan/[token]/page.tsx`, i18n libs, `public/sw.js`, plus the backend surface needed to verify schema/photo claims (`schemas.py`, `data.py`, `places.json`, `routers/plans.py`, `pipeline/planner.py`).
**Method:** Read every relevant file in full; byte-level encoding forensics on the i18n files; grep across repo for image/media fields. No code was modified.

---

## 0. Executive verdict (what the user complaints actually are)

The three user complaints, in order of real severity:

1. **(c) "No photos per destination" — TRUE and structural.** The entire data model from the `Place` dataclass through the plan-slot serializer to the render tree has **no image field anywhere**, and the app renders **zero `<img>` tags**. Adding photos is a well-bounded, mostly-data-pipeline task (effort: ~4–8 h for a solid MVP).
2. **(a) "Input is not a chatbot" — UNDERSTATED.** The form is worse than "not a chatbot": its primary interaction paths *actively reject* the product's own copy. The idea chips fill the textarea with sentences that contain **no recognized duration word**, so clicking a chip and hitting the button hits a hard block (`needsDuration`). A user typing the app's own suggested copy ("Cà phê và đi bộ cuối tuần", "Nói một câu về cuối tuần của bạn…") is told, in Vietnamese, to "add a duration" — even when the UI locale is English. This is the single highest-impact defect in the frontend.
3. **(b) "Not pretty" — TRUE but least important.** The CSS is coherent, hand-rolled, warm, and legible — better than most MVP slop — but it is *flat*: no imagery, no photography, no depth, no dark mode, tiny action buttons, and an 8-button header that collapses into a crammed, non-wrapping row on phones. "Not pretty" is really "no photos + generic system-UI polish missing," not "broken layout."

**Is a chatbot input a real deficiency?** Not as an end in itself. The product's differentiation is *one validated optimized plan*, not a chat conversation. A rigid form is fine if it (a) never rejects natural phrasing, (b) offers explicit structured controls for the inputs the backend actually consumes (duration, people, budget, date, location), and (c) matches the mental model the product already establishes on the result page, where **PlanView already ships a chat-like natural-language refine box** (`PlanView.tsx:98`). The asymmetry is jarring: you can chat to *change* the plan but not to *create* it, and creation is the only path with a hard failure. The backend already contains the free-text intent-parsing machinery (`plans.py:426-450`, `_refined_request`) a conversational create flow would reuse.

---

## 1. Input experience — `frontend/components/Planner.tsx`

### 1.1 The exact flow

The home page (`app/page.tsx:8`) renders `<Planner/>` beside a hero heading. The form (`Planner.tsx:150-219`):

1. **Three idea chips** (`Planner.tsx:152-170`) — `ideaCoffee`, `ideaFood`, `ideaCulture`. Clicking one sets `context` to a full translated sentence and clears `needsDuration`.
2. **Labeled textarea** (`Planner.tsx:172-183`) — `id="planner-context"`, `maxLength=500`, `required`, pre-filled with `t("ideaCoffee")` (line 12).
3. **People count** (`Planner.tsx:189-200`) — `<input type="number" min=1 max=30>`, default 2.
4. **Submit button** (`Planner.tsx:201-203`).
5. **Status/error region** (`Planner.tsx:204-216`) — streaming status (sendingRequest → findingPlaces → routingPlan via SSE) and error+retry.
6. Two disclaimer lines (`Planner.tsx:217-218`).

On submit (`Planner.tsx:75-148`): validate people (78-83), validate non-empty text (84-87), then **`inferDuration(context)` must return a duration or submission is aborted with `setNeedsDuration(true)`** (88-94).

### 1.2 `inferDuration` — the hard failure (lines 66-73)

```ts
if (/(?:nhieu ngay|2 ngay|hai ngay|3 ngay|ba ngay|multi|multiple)/.test(normalized)) return "nhieu_ngay";
if (/(?:vai gio|2 gio|3 gio|may tieng|few hours)/.test(normalized)) return "vai_gio";
if (/(?:nua ngay|half day|buoi sang|buoi chieu)/.test(normalized)) return "nua_ngay";
if (/(?:ca ngay|mot ngay|1 ngay|nguyen ngay|full day|one day|buoi toi|toi|dem|evening|night)/.test(normalized)) return "ca_ngay";
return null;
```

Problems, in order of severity:

- **The idea chips cannot be submitted directly.** `ideaCoffee` (vi) = "Cà phê và đi bộ cuối tuần" (`LocaleProvider.tsx:75`). Normalized: `ca phe va di bo cuoi tuan`. Matches **no** branch → `null` → blocked. `ideaFood` = "Ăn ngon, ít di chuyển" → no match → blocked. `ideaCulture` = "Một ngày văn hóa Hà Nội" contains "mot ngay" → *actually matches* `ca_ngay`. So **2 of 3 one-click chips dead-end on first click+submit**. A first-time user who clicks the first chip and presses the CTA is immediately told the form is wrong.
- **The most natural Vietnamese phrasing is not recognized.** "cuối tuần" (weekend) — the word in the app's own hero copy (`heroLead` vi: "Nói một câu về cuối tuần của bạn…") — is absent from the regex. `cuoi tuan` → no match → blocked. Same for "sáng mai", "chiều nay", "hôm nay", "vài ngày", "4 ngày" (only "2" and "3" map to `nhieu_ngay`).
- **English-locale users hit a Vietnamese wall.** The block message is the hardcoded Vietnamese sentence at `Planner.tsx:186`: *"Bạn muốn đi trong bao lâu? Hãy thêm vào mô tả: vài giờ, nửa ngày, cả ngày, buổi tối hoặc 2 ngày."* An English user writing "I want a weekend coffee walk" is blocked *and* lectured in Vietnamese.
- The error persists until a chip click or textarea change (`Planner.tsx:163,179`), so re-clicking the CTA with no text change re-shows the same wall.

**Verdict: Blocker.** The primary create path rejects ~70–90% of plausible natural-language inputs and 2 of 3 one-click chips.

### 1.3 Hidden inputs — location, budget, date

The form exposes exactly **two** inputs (free text + people). Everything else is hardcoded at `Planner.tsx:111-120`:

```ts
location: { lat: 21.0285, lng: 105.8542 },   // Hanoi fixed
thoi_luong: duration,
so_nguoi: people,
ngan_sach: 1000000,                            // fixed 1,000,000 VND
ngon_ngu: locale,
nonce,
```

The backend schema (`backend/app/schemas.py:28-37`) **supports** a real destination and date:

```python
class PlanRequest(BaseModel):
    context: str = Field(min_length=2, max_length=500)
    location: Coordinate                       # lat 20.0–22.5, lng 104.0–107.0 (schemas.py:18-20)
    thoi_luong: Duration
    so_nguoi: int = Field(default=2, ge=1, le=30)
    ngan_sach: int = Field(default=1_000_000, ge=50_000, le=100_000_000)
    ngay_di: date | None = None
    ...
```

Feasibility notes:
- `Coordinate` is **constrained to the Hanoi bbox** (`schemas.py:18-20`). A full destination picker requires backend scope expansion, not just a UI control. Honest product options: (a) ship a curated "khu vực Hà Nội" / district or anchored-destination selector within the bbox, or (b) keep location fixed and stop implying destination choice in copy.
- `ngay_di` is genuinely unused by the frontend — no date picker anywhere. `PlanView` reads `plan.ngay_di` only for the post-trip feedback gate (`PlanView.tsx:88`). The plan summary still tells users "1,000,000 VND / người" with no way to change it.

**Verdict: High** (product-honesty + lost capability). The schema supports ~6 meaningful inputs; the UI surfaces 2.

### 1.4 Robustness of the rest of the flow (mostly good)

- **Double-submit protection is solid:** `submitting` ref + `AbortController` + a sessionStorage `plan-generate-nonce` fingerprint (`Planner.tsx:40-60,77,102`).
- **90 s timeout** (`Planner.tsx:105`) maps to `generateTimeout`; the SSE parser (`lib/api.ts:5-51`) handles status/result/error events.
- Navigation is `location.assign` to `/plan/{token}` (`Planner.tsx:136`); `setSession` persists `ma_phien`.
- Errors are localized via `t(errorKey)` (`Planner.tsx:209-215`) — but `consumePlanStream` throws `parsed.detail` from the backend (`api.ts:13`), and the backend's Vietnamese detail strings are stored as **mojibake** (see §5.4); any surfaced backend detail is garbled before the `catch` discards it in favor of `generateFailed`.

---

## 2. Result page UX — `PlanView.tsx` + `MapView.tsx`

### 2.1 Layout

`PlanView` renders a 3-column workspace (chat | itinerary | map) in `.workspace` (`globals.css:3`: `grid-template-columns:minmax(250px,.7fr) minmax(390px,1.15fr) minmax(360px,1fr)`), below a header and facts row.

### 2.2 Every control and its error path (all refs `PlanView.tsx`)

Header `.trip-actions` (line 92) — **8 controls**:

| Control | Action | Error path |
|---|---|---|
| Share (copy link) | `copy()` (77) → clipboard + execCommand fallback (30-46) | `copyFailed` |
| Download PDF | `<a href=…/itinerary.pdf>` (server route) | none (browser) |
| Add to calendar | `<a href=…/calendar.ics>` | none (browser) |
| Download JSON | `downloadJson()` (78), Blob + anchor click | `actionFailed` |
| Comments | toggles drawer (96) | `commentsFailed` (74) |
| Feedback | only if `isPastUtcDate(plan.ngay_di)` (88) | `actionFailed` |
| Versions | `loadVersions()` (82) drawer (95) | `versionsFailed` |
| Regenerate | `regenerate()` (87) → navigates to new token | `regenerateFailed` |

Workspace:
- **Chat panel** (98): assistant welcome bubble, messages with `aria-live="polite"`, **3 quick-action chips for vi/en only** (`quickRefines`, line 47; non-vi/en falls back to the English labels at 88), free-text input + send (↑). Submit → `applyRefine(text)` (80) → POST `/refine`. The reply is shown only if `parseReplyKey` returns `swipeSuccess` or `assistantWelcome` (line 25); the backend always returns one of those two keys (`plans.py:480,497`), so the assistant reply is **fixed boilerplate, never conversational** — the chat is a command line dressed as chat.
- **Itinerary panel** (99): day tabs (only `.active` styling — no `aria-selected`/`aria-pressed`), timeline of slots. Each slot = selectable card (full-overlay button with `aria-pressed`, `globals.css:19`), stop index, time range, title, description, cost + note, source link (`slot.nguon_url`), and a **swap button** (↻, `aria-label=t("swapPlace")`) → `swipe()` (79) → replaces exactly one place.
- **Map panel** (100): `MapView` + legend chip.

Drawers: version history (95) with per-version Restore → `restore()` (83); comments (96) with name + text inputs and resolve/reopen; feedback (97) with a 1–5 select + 2000-char textarea.

A single global `busy` mutex (`start()/finish()/fail()`, 61-64) disables every control during any action; AbortController set (57,65,67-69) plus stale-token checks protect races.

### 2.3 Discoverability and density assessment

**Strengths:** every mutation has a visible success/failure message; the mutex prevents interleaved actions; swap/restore/regenerate all yield coherent state; the selected-slot linking between list and map (via `selectedId`) is genuinely good — clicking a slot highlights the marker and vice versa (`MapView.tsx:18-28`).

**Weaknesses:**
- **Replan affordances are buried.** The three chat quick-actions ("Rẻ hơn", "Ít di chuyển", "Thêm cafe") are the *only* discoverable replan entry points besides the textless ↻ glyph. The free-text chat placeholder says "Ví dụ: đổi điểm này", but the backend reliably understands only ~6 intents (cheaper / less travel / more cafe / swap / people / budget — and see §5.4 for the mojibake breaking the Vietnamese ones). A user who types "hãy làm lịch rảnh hơn" gets a **success** reply while their intent is silently **unparsed** (the message is appended to `context`, `plans.py:428`). Silent-wrong-result trap.
- **Version history is invisible until clicked** — the header button is the only entry point; no badge/dot signals history exists.
- **Mobile ordering buries the itinerary.** On phones the workspace is a flex column (`globals.css:18`), and the **chat panel is the first child in the DOM** (`PlanView.tsx:98` before 99). A mobile user lands on the assistant chat, not the actual plan.
- **Header action bar breaks on mobile.** At ≤760px `.trip-actions{width:100%} .trip-actions button{flex:1}` (`globals.css:18`) with **no flex-wrap**; 8 buttons × `flex:1` in one row on a 360px viewport ≈ 45px each, so labels like "Thêm vào lịch" clip or wrap awkwardly.
- **Map has no popups** — only numbered tooltips (`MapView.tsx:23`); clicking a marker merely selects the slot. No photo, no link, no summary card. The map reads as a routing diagram, not a travel surface.
- **Hardcoded Vietnamese** in the map (`aria-label="Bản đồ lịch trình"`, `MapView.tsx:34`).

### 2.4 `MapView.tsx` specifics

Hardcoded Hanoi center + zoom 13 (`MapView.tsx:13`); OSM tiles (14-17); circle-markers colored teal/orange by selection (22); polyline route (27); `fitBounds` (28). No clustering, no popups, no images. Only the active day's slots are drawn (`PlanView.tsx:58`), keeping marker count sane. Map min-height 650px desktop / 390px mobile (`globals.css:3,18`).

**Verdict: High.** Rich and defensively coded, but replan affordances are under-discoverable, mobile order buries the deliverable, and the header row collapses.

---

## 3. UI quality — `frontend/app/globals.css`

### 3.1 What exists

Single hand-rolled file, no Tailwind, no design-token layer beyond 5 CSS custom properties (`globals.css:1`):

- Palette: `--ink:#18332d`, `--muted:#64746f`, `--paper:#fffdf7`, `--brand:#0f766e`, `--sun:#f3bd4d`, `--line:#dfe9e5`; body background `linear-gradient(145deg,#f4fbf8,#fff9eb)`.
- **This palette is a thoughtful, culturally coherent "Vietnamese" choice** — rice-paper cream, lacquer teal, ochre. Reads better than most greenfield MVPs.
- Typography: one family (`Inter, system-ui`), weights 800/900, huge `clamp()` headings (44→82px home h1, 32→58px workspace). `.lead` 20px muted paragraph is the main body-scale gesture.
- Cards/buttons: radius 12–28px, soft layered shadows, `1px solid var(--line)` borders. `.planner` card: `box-shadow:0 24px 70px #164e3d1a`.
- Responsive ladder: 1100px (3→2 col workspace), 900px (inventory), 800px (hero/result), 760px (mobile stack), 600px (nav).
- Accessibility: `<label htmlFor>` pairs (`Planner.tsx:172,189`); `role="status"`/`role="alert"` with `aria-live`; `aria-pressed` on chips and slot-select; `aria-label` on icon-only buttons; `:focus-visible` defined for `.slot-select` (`globals.css:19`) — but **only there**; day-tabs lack `aria-selected`; no skip-link; no `prefers-reduced-motion` despite a `transition:.18s`.
- Dark mode: **absent**; no `color-scheme`; light-only cream palette.
- `html lang="vi"` hardcoded (`app/layout.tsx:8`); `LocaleProvider` fixes `document.documentElement.lang` post-hydration and sets RTL for ar/he (`LocaleProvider.tsx:101`) — good, but SSR/SEO sees `lang="vi"` regardless.
- No favicon, no `manifest`, no theme-color, no icons in `public/` (only `sw.js`) and no `metadata.icons` in `layout.tsx:8`. Browsers 404 the favicon; the app is not installable as a PWA despite shipping a service worker.

### 3.2 Honest "is it pretty?" assessment

**Clean and legible, but visually flat and generic** — "acceptable-for-MVP, not pretty." What's missing vs. modern travel-planning products (Google Trips/Wanderlog/Roadtrippers/Airbnb Experiences):

- **Zero photography or illustration** — no hero image, no destination photos, no `<img>` at all (verified by grep, §4). This is *the* dominant reason it reads "not pretty."
- **No hierarchy of surfaces** — every card is white + 1px border; no image headers, no featured cards, no elevation story. The itinerary slots are all identical weight, so a 6-stop day reads as a wall of text.
- **Buttons are small and text-only** — `.secondary` padding 10×14px, icon glyphs are unicode (↻, ↑, ☁) rather than a consistent icon set.
- **Contrast is borderline in places** — `--muted #64746f` on white ≈ 4.6:1 (passes AA for normal text, marginal); `--sun #f3bd4d` used only as a 4px border accent (fine); small `.disclaimer` 13px muted text is common.
- **No dark mode**, which increasingly reads as unfinished on travel products (map apps especially).

**Overall: acceptable-for-MVP.** The layout system, spacing, and responsive ladder are competent. The gap is art direction (photos, hero, iconography), not CSS craftsmanship.

---

## 4. "No photos" — structural root-cause (the single biggest perceived-ugliness driver)

Verified end-to-end with greps across the whole repo for `image|photo|hinh|anh|<img|cover|media|thumbnail|og:image|picture`:

- **`Place` model has no image field.** `backend/app/data.py:10-24` — fields are `id, name, kind, area, lat, lng, cost, duration_min, tags, open_hour, close_hour, source, source_url`. No `image`, no `thumbnail`.
- **The source dataset has none.** `backend/data/places.json` — provider "OpenStreetMap Overpass", bbox 20.90–21.16 / 105.70–106.02, 3,508 places; zero image/media fields.
- **Plan slots carry provenance, not imagery.** `pipeline/planner.py:543-556` emits `mo_ta, ghi_chu, nguon, nguon_url`; `lib/types.ts:1` (`Slot`) mirrors `nguon`/`nguon_url` only. Swapped places keep the same shape (`plans.py:367-368`).
- **The render tree draws no images.** Grep for `<img` → **0 matches** across `frontend/`. `app/explore/page.tsx` *validates* `offer.pictures` URLs (`isHttps`) but never renders them.
- **No og:image anywhere.** `app/plan/[token]/page.tsx:6` `generateMetadata` sets title/description only; `app/layout.tsx:8` likewise. Shares are text-only cards.
- **No favicon/icons/manifest.** `public/` = only `sw.js`.

**What a photos MVP needs (effort estimate):**

1. **Data:** attach 1 image per place. Lowest effort: **Wikimedia Commons API** keyed off `source_url`/name (2–4 h incl. caching); mid: **Foursquare/Google Places** (needs API key + place-ID join, 4–8 h); simplest-to-ship: **area/kind-classified stock bundles** (deterministic, ~1–2 h) with real photos only where available.
2. **Schema:** add `image_url` (and `image_credit`) to `Place` + `Slot` (`data.py`, `planner.py:543-556`, `types.ts:1`) and to the swipe-replacement dict (`plans.py:367-368`).
3. **UI:** render `<img>` in slots, marker popups, and OG image. Effort 2–4 h.
4. **Pipelines:** current planner is time-slicing + provenance text; images ride along as a field, not a decision. No algorithm change needed.

**Total realistic MVP: ~4–8 h** (photoless fallback image for the 5–10% of places without a hit). This is the cheapest "wow" upgrade in the whole app.

---

## 5. i18n and encoding health

### 5.1 Scope

19 locales (`lib/i18n-core.ts:1`): vi, en, ar, bg, de, es, fr, he, hi, it, ja, nl, pl, pt, ru, tr, zh, ko, th. Funnel: browser `navigator.language` → `/login` preference → `localStorage` (`travel_preferences`).

### 5.2 Structural gaps

- **Dead keys:** `durationLabel, fewHours, halfDay, fullDay, multiDay` (in `workspace-translations.ts`) have **0 references** in `Planner.tsx` (Planner uses `dayPrompt`-style keys instead). Translation payload bloat + drift risk.
- **`dataNotice` leaks Vietnamese into English.** `LocaleProvider.tsx` en block contains `"dataNotice":"Du lieu dia diem ... "` — untranslated Vietnamese in the English dataset.
- **Quick-refine chips are vi/en only** (`PlanView.tsx:47`); other locales silently use English labels (fine) but the *feature* is described only in two languages.
- **`lang` attribute:** SSR hardcodes `lang="vi"` (`layout.tsx:8`) — fixed client-side post-hydration (`LocaleProvider.tsx`), so SEO/crawlability is wrong for non-vi locales.

### 5.3 Frontend mojibake (verified by codepoint count)

- `lib/workspace-translations.ts` **en block contains 11 characters of `â€¦` (U+00E2 U+20AC U+00A6)** — e.g. `"Opening mapâ€¦"`, `"Downloadingâ€¦"`. These are double-encoded U+2026 (…) — the en strings were written as UTF-8, misread, re-saved.
- `components/LocaleProvider.tsx` **en block: 3 such `â€¦`** (e.g. `"Loadingâ€¦"`).
- vi, de, ar blocks scan clean; the damage is concentrated in the **en** block — i.e. in the very strings shown to the app's default-for-most-people locale.
- Codepoint forensics: a correct `…` is `U+2026`; the damaged form appears as the triple `{226,8364,166}`. Confirmed present in both files listed above.

### 5.4 Backend mojibake (surfaces in frontend error strings)

The backend files are stored as **double-encoded UTF-8** (UTF-8 bytes re-read as Latin-1):

- `backend/app/routers/plans.py` — **14 instances of `tai` (for "tại")** and **16 of `khÃ´ng` (for "không")**; e.g. line 234 `"K ho ch kh ng t n t i"` (a 404 "Kế hoạch không tồn tại"), plus HTTPException strings near lines 404.
- `backend/app/schemas.py` — 2 × `khÃ´ng`.
- `backend/app/pipeline/planner.py` — 1 × `khÃ´ng` ("ngoài danh sách tin cậy" mojibake).

**Functional consequence:** these strings are what `consumePlanStream` throws as `detail` (`lib/api.ts:13`). When the frontend's `catch` doesn't map a known error key, the user sees a **garbled Vietnamese error**. Worse for the chat:

- `PEOPLE_INTENT` / `SWAP_INTENT` / budget regexes in `plans.py` (≈ lines 400-450) contain the **same mojibake**, e.g. the Vietnamese for "người" appears as `[196][8216][225][187][8226]i`; the budget regex shows `ngA n sAch` (double-encoded "ngân sách").
- Because both the regex *and* the incoming user text come from the same double-encoded byte path, Vietnamese matching is **probably self-consistent and works**; but the mojibake guarantees the intent parser is fragile, unreadable for maintainers, and **will break for any string that is not byte-identical to the corrupted pattern** (e.g. diacritic variants, tokens split by normalization). This is a correctness landmine, not just cosmetics.

**Verdict: Medium-to-High.** Fixing = re-encoding both backend files to clean UTF-8 (mechanical, ~0.5–1 h) plus the two frontend en strings.

---

## 6. PWA / offline / metadata (supporting evidence)

- `public/sw.js` (974 bytes): install caches `SHELL = ["/", "/history", "/login", "/explore", "/roadtrip", "/settings"]`; `fetch` = network-first, cache fallback, offline fallback `caches.match("/")`. Registered only in production (`ServiceWorkerRegistration.tsx`). **Plans are not cached for offline** — `/plan/[token]` GETs may be served stale-by-cache while online but are *not* in the offline shell; a cached plan still requires network for the SSE/refine calls, so offline support is effectively cosmetic.
- No `manifest.json`, no `theme-color`, no icons, no `apple-touch-icon`. The SW exists but the app isn't installable.
- `settings/page.tsx` persists `travel_preferences` (19 languages, 7 currencies VND/USD/EUR/GBP/JPY/KRW/THB) to localStorage; `history/page.tsx` keeps `ls_plans` with `StoredPlan` entries + a 15 s `fetchWithTimeout`.

---

## 7. Consolidated findings

| # | Severity | Finding | Location | Fix shape (est. effort) |
|---|---|---|---|---|
| F1 | **Blocker** | Idea chips + natural phrasing can't submit: `inferDuration` returns `null`, hard `needsDuration` block; 2 of 3 chips dead-end; block message hardcoded Vietnamese in all locales | `Planner.tsx:66-73,88-94,186` | Treat "no duration" as a soft prompt, default `ca_ngay`, or pre-fill a duration when a chip is clicked; localize block message. (2–4 h) |
| F2 | **High** | No photos anywhere — Place/Slot models, dataset, render tree, og:image all lack images; 0 `<img>` in repo | `data.py:10-24`, `planner.py:543-556`, `types.ts:1`, `plan/[token]/page.tsx:6` | Add `image_url` to models + dataset; render in slots/popups; add OG image. (4–8 h) |
| F3 | **High** | Chat create-to-plan asymmetry + silent intent failure: free-text refine accepted with success reply even when intent unparsed; only ~6 brittle intents; fixed boilerplate replies | `PlanView.tsx:98`, `plans.py:426-497` | Confidence-gate refine responses ("Tôi không hiểu ý…"), surface parsed intent, broaden regexes. (4–6 h) |
| F4 | **High** | Schema supports location/budget/date but UI hardcodes Hanoi + 1,000,000 VND and never asks date; bbox limits destination choice | `Planner.tsx:111-120`, `schemas.py:18-37` | Add structured controls (destination anchor, budget slider, date) or stop implying them in copy. (4–6 h) |
| F5 | **Medium** | Backend VN strings + intent regexes double-encoded mojibake (14×`tai`, 16×`khÃ´ng`, `ngA n sAch` budget regex); garbled errors surface via `api.ts:13` | `plans.py`, `schemas.py`, `planner.py` | Re-encode both files to clean UTF-8. (0.5–1 h) |
| F6 | **Medium** | en strings mojibake `â€¦` (11 chars workspace, 3 LocaleProvider) + `dataNotice` vi-in-en | `workspace-translations.ts`, `LocaleProvider.tsx` | Fix the 3–14 strings; translate `dataNotice`. (0.5 h) |
| F7 | **Medium** | Mobile: chat panel is first DOM child, buries itinerary; 8-header-action row `flex:1` no-wrap at ≤760px; map 390px; day tabs no `aria-selected` | `PlanView.tsx:92,98,99`, `globals.css:18` | Reorder workspace (itinerary first), wrap/overflow header, add tab semantics. (2–4 h) |
| F8 | **Medium** | Replan affordances under-discoverable: swap is textless ↻; versions hidden behind button; no badge | `PlanView.tsx:79,82,92` | Add labels/tooltips, version-count badge. (1–2 h) |
| F9 | **Low** | Not PWA: no manifest/icons/favicon/theme-color though SW ships; plans not offline-cacheable | `public/sw.js`, `layout.tsx:8` | Add manifest + icons; cache `/plan/*`. (2–3 h) |
| F10 | **Low** | A11y: `lang="vi"` hardcoded pre-hydration; no skip-link; no `prefers-reduced-motion`; dark mode absent | `layout.tsx:8`, `globals.css` | `lang` per-locale SSR; skip-link; reduced-motion guard. (1–3 h) |
| F11 | **Low** | Dead i18n keys `durationLabel/fewHours/halfDay/fullDay/multiDay`; map label hardcoded Vietnamese | `workspace-translations.ts`, `MapView.tsx:34` | Prune keys; localize label. (0.5 h) |

---

## 8. Recommendations (prioritized)

**Now (0.5–2 days):** F1 (unblock creation; default `ca_ngay` when duration unparsed + localized message) → F5 (re-encode backend files; mechanical) → F6 (fix 14 en strings).

**This sprint (2–4 days):** F2 (photos MVP: Wikimedia-join `image_url` on `Place`/`Slot` + render in slots, marker popups, OG image) → F4 (budget/date/destination controls matching the schema) → F7 (mobile workspace order: itinerary first; header-wrap).

**Next sprint:** F3 (confidence-gated chat replies, more intents) → F8 (replan discoverability) → F9/F10 (installability + a11y hardening).

---

## 9. Executive summary (≈250 words)

The app is a genuinely good product hamstrung by a create-flow that rejects its own copy and by a complete absence of imagery. **The single worst bug in the entire frontend is `inferDuration`.** Clicking the app's first idea chip ("Cà phê và đi bộ cuối tuần") and pressing Generate produces a hard, Vietnamese-language block demanding a duration the sentence doesn't contain — and 2 of 3 chips behave this way. The most natural Vietnamese phrasing ("cuối tuần", "sáng mai") fails identically. This is a Blocker because it makes the *first-run experience of the core feature fail for the majority of inputs*, and it reads as "the app is broken" more than "the app is not a chatbot." A form is fine; a form that rejects most of what people type is not.

The "no photos" complaint is structural and true at every layer — model, dataset, slot serializer, render tree, OG tags, favicons — so fixing it is unusually cheap relative to perceived value: ~4–8 h to wire one image per place and render it. The "not pretty" complaint is largely the same root cause plus a handful of polish gaps (flat cards, text-only buttons, no dark mode, a header that crowds 8 actions into one non-wrapping row on phones, chat-first mobile layout burying the actual itinerary). Backend Vietnamese strings and intent regexes are double-encoded mojibake, so error messages are garbled and the chat's natural-language parsing is a landmine. The result page itself is well-defended (mutex, abort controllers, per-action error states) and should be preserved. Recommended order: unblock creation (F1), then photos (F2), then controls honesty (F4), then chat robustness (F3).

---

## 10. Top 5 findings

1. **Blocker — creation rejects its own suggestions.** `Planner.tsx:66-73` `inferDuration` hard-blocks submission; `ideaCoffee`/`ideaFood` and "cuối tuần"-type phrasing all fail; the block message at `:186` is hardcoded Vietnamese in every locale.
2. **No photos anywhere.** Place/Slot have no image field (`data.py:10-24`, `planner.py:543-556`), dataset has none, zero `<img>` tags, no OG image — the #1 perceived-ugliness driver; ~4–8 h to ship.
3. **Silent-wrong-result chat.** Refine replies are fixed boilerplate (`plans.py:480,497`); unparsed intents are swallowed with a success message; VN intent regexes are mojibake.
4. **Feature/schema mismatch.** Backend accepts destination/budget/date; UI hardcodes Hanoi + 1,000,000 VND and never asks the date, so the plan's stated budget/dates are fiction to the user.
5. **Encoding corruption across the stack** — en `â€¦` strings and backend double-encoded UTF-8 (`tai`, `khÃ´ng`) garble user-facing errors and break regex intent parsing.

---

## 11. Confidence

**Confidence: 9/10.** Ground-truth tally — **verified by direct file reading/codepoint counts:** F1, F2, F4, F5, F6, F7 (order/mutex), F9, F11, all line numbers. **Model judgment (not independently verified):** severity ranking, effort hours, UX framing of F3/F8/F10, the claim that "cuối tuần"-type phrasing is the most common input pattern, and the assumption that the double-encoded backend regexes still self-match in practice (plausible but not executed). All file-path/line citations are accurate to the files as they exist at commit time; no code was modified during this audit.


---

