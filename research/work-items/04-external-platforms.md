# Work Item 04 — Đưa người dùng ra ngoài đúng chỗ: external-platform navigation (Google / Maps / TikTok / Nguồn)

**Lane:** Navigating users to external platforms (Google Search, Google Maps, TikTok, source sites).
**Repo:** `D:\Code\aithucchien\ai_travel` (FastAPI backend + Next.js frontend).
**Scope boundary:** This lane designs the *redirect/link surface only*. Image urls, wiki/wikidata tags, and amenity enrichment belong to Lane 3 (data/images); itinerary changes belong to Lane 2; manual place swap to Lane 5; visit-duration display to Lane 6. Code is **not** modified (research-only).
**Date:** 2026-08-11.

---

## 1. Files read (evidence base)

| Subject | File:line | What it establishes |
|---|---|---|
| Slot factory | `backend/app/pipeline/planner.py:1075-1093` | Each slot dict carries `nguon` (source name string) and `nguon_url` (source permalink). Also `:1261-1264`, `:1307-1310` (replacement + refine paths). |
| Place dataclass | `backend/app/data.py:11-26` | `Place` has `source` (default `"demo"`) and `source_url` (default `None`); also `tags`, `image_url`, `image_credit`. **No** `website`/`phone`/`address`/`wikipedia` fields. |
| Local place load | `backend/app/data.py:97-113` | `_load_imported_places` builds `Place` from `places.json` but only maps `source`/`source_url`; the JSON's `website`, `phone`, `address` fields are **silently dropped**. |
| Curated anchor places | `backend/app/data.py:121-222`, `:224-300` | All curated/demo places are constructed with `source_url=None` → in local+curated mode these slots render **no** source link. |
| OSM import | `backend/scripts/import_osm_places.py:88-115` | Captures `website`/`phone`/`address` and `source_url = https://www.openstreetmap.org/{type}/{id}`; feature tags limited to cuisine/outdoor_seating/wheelchair/tourism/leisure/historic. No wikipedia/wikidata capture. |
| Dataset coverage | `backend/data/places.json` (3508 POIs) | Source coverage: **3508/3508 (100%)** have `source_url` (all OSM permalinks). 270 (≈7.7%) have `website`, 543 (≈15.5%) have `phone`, **0** wiki-tagged. |
| Postgres catalogue | `backend/app/data.py:310-335` | `nguon_url` from the `dia_diem` table → source link present for OSM rows in prod too. |
| Plan view slot rendering | `frontend/components/PlanView.tsx:235` | Existing external anchor (the **only** one on the plan page): `<a className="source" href={slot.nguon_url} target="_blank" rel="noreferrer">` under `{slot.nguon_url && …}`. Uses `noreferrer` only (implicit noopener). |
| Map markers | `frontend/components/MapView.tsx:37-45` | `bindTooltip`/`bindPopup` with raw HTML string (img + strong). **No links** in popups. Popup maxWidth 260. |
| Inventory (prior art) | `frontend/app/explore/page.tsx:66` | Booking link uses `target="_blank" rel="noopener noreferrer"` — the repo's established safe-anchor pattern. |
| Admin | `frontend/app/admin/page.tsx:494,513` | Source links `target="_blank" rel="noreferrer"`. |
| CSP / headers | `frontend/next.config.mjs:13-20` | `Referrer-Policy: strict-origin-when-cross-origin`; CSP has **no** `navigate-to` and `default-src 'self'` does **not** govern top-level link navigation → external https anchors render and navigate fine. `img-src … https:` and `connect-src … https:` already allow external hosts. |
| Slot CSS (click gotcha) | `frontend/app/globals.css:26` | `.slot-select` covers the whole card (`inset:0`); siblings get `position:relative; z-index:2` and `pointer-events:none`. Only `.source` and `.icon-action` are re-enabled (`z-index:3; pointer-events:auto`), and `.slot-actions` (line 65) opts in. **Any new links must live inside `.slot-actions` or carry the same opt-in classes** or they will be unclickable. |
| Frontend types | `frontend/lib/types.ts:1` | `Slot` exposes `nguon?`, `nguon_url?`, `toa_do` (lat/lng), `loai`, `ten_dia_diem`. **No** area/address on the frontend slot. |
| PDF link policy | `backend/app/services/pdf_export.py:129-133` | Proven pattern: only render the source link if it `startswith("https://")`, HTML-escaped. |
| Spec constraint (Amadeus) | Spec text | "chỉ giữ HTTPS provider link" — external links must be strict-https only, never fabricated. |

---

## 2. Current external-link surface — inventory and gaps

### What exists today
1. **Plan slot → "Nguồn"** (`PlanView.tsx:235`): renders whenever `slot.nguon_url` is a truthy string. In the 3508-POI OSM catalogue every slot has one (an OSM permalink); curated fallback places (`curated-*`) have `None` → no link, and the label falls back to `nguon || nguon_url`. In local demo mode (`data.py:79-92`) legacy demo places default to `source="demo"`, `source_url=None`, so most local-mode slots show no link unless `places.json` is loaded.
2. **Explore booking links** (`explore/page.tsx:66`) — the correct reference implementation for attribute hygiene.
3. **Admin source links** (admin page) — same pattern.
4. **Map popups** — image + name only; zero links (MapView.tsx:41-45).

### Gaps
- **G1. No Google (Search/Maps) or TikTok surface anywhere** in the app. Users cannot jump to the place card, get directions, or watch TikTok clips about a stop. The plan page is a dead end for "show me this on a real map / what do people say about it".
- **G2. Map markers have no links at all** — the map is where users most want "open in Maps".
- **G3. `rel="noreferrer"` only** on the source link. Fine (noreferrer ⇒ noopener, MDN/OWASP, [S6][S7]), but the repo's own explore page already uses the stronger `noopener noreferrer`; the slot link is inconsistent and, more importantly, has **no scheme allowlist** — `nguon_url` comes from the backend, but defensive client-side filtering (https-only, per `pdf_export.py:130-133` precedent) is absent.
- **G4. Data drop:** `website`/`phone` (270/543 places) and `address` exist in `places.json` but never reach the API (data.py:97-113 drops them). Slot schema lacks `khu_vuc`/`address`, which the Google place card (`query=PLACE_NAME,ADDRESS`) wants. Wiki/wikidata tags are not captured at import (import_osm_places.py:88-95), so no Wikipedia links are possible today.
- **G5. No token-leak control specific to outbound links** — currently benign because links contain no query params, but the design must never append the share token as a URL parameter (it is a capability token; exposing it in a Referer/query would let an external site replay the read-only plan).

**Verdict:** The redirect surface is functionally **1.5 links** (one per OSM slot, none on the map). Everything in this work item except the existing "Nguồn" anchor is net-new.

---

## 3. Ground truth — URL formats (confirmed 2026)

### 3.1 Google Maps (place card / search)
- Official Maps URLs guide (Google developers) [S1]: `https://www.google.com/maps/search/?api=1&query=<value>` with **`api=1` required**. `query` accepts a place name, an address, or comma-separated `lat,lng`; the comma inside the value must be percent-encoded (`%2C`), spaces as `+` or `%20`. Max URL length 2,048 chars. Search-by-coordinates alone drops into a bare pin ("no additional place information"); recommended for a *place card*: `query=PLACE_NAME,ADDRESS`, or `query=PLACE_NAME&query_place_id=…`. (We have no place IDs in the catalogue, so name+area / name+address is the practical form.)
- Coordinate form corroborated independently: `google.com/maps/search/?api=1&query=48.8584,2.2945` documented in the 2026 GoToAppleMaps URL-format guide [S2].
- Directions: `https://www.google.com/maps/dir/?api=1&origin=<o>&destination=<d>` [S1]; **both** `origin` and `destination` may be lat/lng, and `origin` is optional — if omitted, "Defaults to most relevant starting location, such as device location". So a "chỉ đường" link needs only one string: `https://www.google.com/maps/dir/?api=1&destination=<urlencode(lat,lng)>`.
- Legacy `/maps?q=lat,lng` (no `api=1`, `maps.google.com/?q=…`) is widely documented and still resolves [S2][S12], but the official `api=1` family is the supported, recommended form. **Use `api=1` only.**
- Google explicitly encourages `utm_source`/`utm_campaign` on these URLs for analytics [S1] — optional; see §5 for the no-PII decision.

### 3.2 Google Search
- `https://www.google.com/search?q=<urlencoded>` is the standard results URL; `q` is the query, `hl` the interface language, `gl` the country context [S3][S13]. Independent 2026 references agree `q` is documented/stable [S3][S4]. `udm=14` (web-results mode without AI overviews) exists but is **undocumented/reverse-engineered** — do not depend on it at MVP (mark **unverified — confirm at implementation time** if we ever want it).

### 3.3 TikTok search
- Official web lander is `https://www.tiktok.com/search` (page title "Find '' on TikTok") [S5]. The query-string form `https://www.tiktok.com/search?q=<urlencoded>` appears verbatim in independent 2026 tooling/docs (SocialKit example "QUERY https://www.tiktok.com/search?q=funny+cats") [S8] and is the `startUrls` form accepted by TikTok-search scrapers [S9].
- **Caution:** TikTok does **not** officially document this deep-link format; it is reverse-engineered/observed. Mark **unverified — confirm at implementation time** (open once, check the search page renders the queried term). On mobile, the URL tends to hand off into the native-app search via universal links when the app is installed, else falls back to the mobile-web search page [S10] — acceptable either way.

### 3.4 Anchor safety (reverse tabnabbing / referrer)
- `target="_blank"` without `rel="noopener"` lets the opened page read `window.opener` and redirect the app tab (OWASP WSTG-CLNT-14) [S7]. Fix: `rel="noopener noreferrer"` on every external anchor. `noreferrer` implies `noopener`, so the existing slot link is *not* vulnerable in modern browsers [S6][S7], but adding both is the consistent, audit-friendly form.
- `Referrer-Policy: strict-origin-when-cross-origin` (already set at `next.config.mjs:16`): cross-origin navigations send **only the origin** (scheme+host), never the path/query [S11]. Since the share token lives in the **path** (`/plan/{token}`), it is **not** leaked to Google/TikTok/OSM by the Referer today, and this is a hard guarantee we should preserve (never move the token into a query string).

### 3.5 Source links (OSM)
- `nguon_url` is always `https://www.openstreetmap.org/{node|way|relation}/{id}` (import_osm_places.py:114, osm_verify.py:198) — a valid, licence-clean, deep-linkable permalink. ODbL attribution is already on the map layer (`MapView.tsx:18`) and in the popup-less legend. No fabrication risk: URLs come from **data**, only ever rendered through a https-only client filter.

---

## 4. Design

### 4.1 Guiding constraints (derived from spec + findings)
1. **Never fabricate URLs.** Every outbound href is built by a deterministic client-side function from data already on the slot (`ten_dia_diem`, `toa_do`). The LLM never emits link strings; the pipeline already preserves `nguon_url` verbatim (`services/ai.py:335-336`).
2. **Never leak the token.** Outbound URLs contain only slot data + static constants (no `token`, no plan id, no `ma_phien`, no user session). Global Referrer-Policy already strips the path (§3.4). If we adopt `utm_source`, it must be the constant string `minhdidau` (app name), never per-user data.
3. **HTTPS-only + sanitized.** All outbound hrefs must pass an allowlist: `new URL(url)` and `protocol === "https:"` (mirrors `pdf_export.py:130-133`). No `javascript:`/`data:`/`tel:` for MVP.
4. **Attributes:** `target="_blank" rel="noopener noreferrer"` (+ `referrerPolicy="no-referrer"` where we want zero referrer, e.g. Google/TikTok). CSP needs no change (no `navigate-to`; `default-src` doesn't gate anchors, §1).
5. **Rendered as text, HTML sanitized:** slot text is plain strings (no `dangerouslySetInnerHTML` in PlanView); the map popup is the one place that builds HTML strings (MapView.tsx:42) — new popup links must be assembled via `encodeURIComponent` + a tiny allowlist function, never raw user/AI text.

### 4.2 Minimal data work (no schema change required)
The frontend `Slot` already carries everything for the two highest-value links: `ten_dia_diem` (name) and `toa_do` (lat/lng).
- **Google Maps place card:** prefer `query=<name>, <area>` when area exists; with the current slot it falls back to `query=<lat>,<lng>` (bare pin per [S1]). **Recommended minimal backend addition (sync with Lane 3):** include `khu_vuc` (already present on `Place.area`) and, when available, the OSM `address` string into the slot payload so the card gets `query=NAME, AREA` (secondary: append `, Hà Nội` — Hanoi-only MVP). This is a one-line slot-factory change (planner.py:1075-1093) + one-line TS type (types.ts:1). Do **not** surface `phone`/`website` in this work item (privacy + Lane 3 remit); source_url remains the "Nguồn" target.
- **Directions:** `https://www.google.com/maps/dir/?api=1&destination=<encodeURIComponent(lat + "," + lng)>&travelmode=walking` (travelmode is an accepted Maps-URL nicety; `api=1` + destination are the documented core [S1]).

URL builder sketch (pure function, client-side module, e.g. `frontend/lib/external-links.ts`):
```ts
const KM = "https://www.google.com/maps/search/?api=1&query=";
const DIR = "https://www.google.com/maps/dir/?api=1&destination=";
const GS  = "https://www.google.com/search?q=";
const TT  = "https://www.tiktok.com/search?q=";
export function mapsPlace(slot){return KM + encodeURIComponent(`${slot.ten_dia_diem}, ${slot.khu_vuc ?? "Hà Nội"}`)}
export function mapsCoords(slot){return KM + `${slot.toa_do.lat}%2C${slot.toa_do.lng}`}   // documented §3.1
export function mapsDir(slot){return DIR + `${slot.toa_do.lat}%2C${slot.toa_do.lng}&travelmode=walking`}
export function googleSearch(t){return GS + encodeURIComponent(t)}
export function tiktokSearch(t){return TT + encodeURIComponent(t)}
```
Recommendation: use **coords-first** for the "bản đồ" action (guaranteed correct pin, [S1] Example 2) and offer the *card* variant by appending the name after the pin as plain text context is not supported — so choose one: `mapsPlace` (friendlier card; risk of wrong-geocode for generic names like "Café Đinh") **or** `mapsCoords` (certain pin, no place-info panel). **MVP decision: `mapsCoords` for reliability + a Google Search link (`googleSearch(ten_dia_diem + " Hà Nội")`) as the “tìm thêm” action.** Document both in code comments; swap to name+area card after Lane 3 delivers `khu_vuc` reliably.

### 4.3 Per-slot action row (PlanView.tsx:235-272 area)
Extend the existing `slot-actions` block (currently the swap/delete buttons, globals.css:65). Because the whole card is covered by `.slot-select`, any anchor added here is automatically `pointer-events:auto` — no CSS magic needed beyond keeping them **inside** `.slot-actions` (or giving them `.icon-action`-style classes).

Recommended UI (churn-aware, §5):
- One **primary** action: `Xem trên Google Maps` (icon pin + label) → `mapsCoords`.
- One **secondary**: `Chỉ đường` → `mapsDir`.
- One **optional/social**: `TikTok` → `tiktokSearch(name)` (Vietnamese audience skews TikTok-heavy; confirm the format at implementation, §3.3).
- Existing `Nguồn` stays (rel upgraded to `noopener noreferrer`).
- Keep it to ≤4 anchors; render as text links branded with the target domain name, not raw URLs, and add i18n keys (rollout across all 19 locales in `workspace-translations.ts`, keys in `i18n-core.ts:9`).

Anchor component (shared, tiny):
```tsx
function Outbound({href,label}:{href:string|undefined;label:string}){
  if(!href) return null;
  const u = (()=>{try{return new URL(href)}catch{return null}})();
  if(!u || u.protocol!=="https:") return null;                 // https-only, §4.1(3)
  return <a href={u.href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{label}</a>;
}
```

### 4.4 Map markers (MapView.tsx:41-45)
Add the same 2 actions to the popup HTML string. **Sanitization is mandatory** because popup content is an HTML string:
- Name already interpolated — keep `slot.ten_dia_diem` text as-is (it is sanitized server-side at authoring; add a defensive `textContent`-style escape helper anyway, or better: construct the popup via a `document.createElement` sequence instead of string concat — minimal change and removes the XSS surface entirely).
- Append two links: "Google Maps" and "Chỉ đường", reusing the same builders. `target=_blank rel=noopener noreferrer` inside popup HTML — Leaflet renders it in the map pane; the popup is a sibling of the map, clicks are independent, but bump `maxWidth` from 260 → 300 and add ≥44px touch targets for mobile (globals.css `.map-popup a`).

### 4.5 Mobile behavior
- Google Maps URLs are universal links: tapping a Maps URL on iOS/Android launches the native app when installed, else the browser [S1][S2]. No UA sniffing needed.
- TikTok: `tiktok.com/search?q=` may hand off into the app or land on the mobile-web search page [S10]; acceptable.
- All anchors `target="_blank"` — on mobile browsers this behaves as expected (new tab / external browser hand-off); nothing to special-case.

### 4.6 Avoid leaking the token session
- No outbound URL carries `token`, `ma_phien`, or user identity (§4.1.2).
- `referrerPolicy="no-referrer"` on the anchors *plus* the global header gives a zero-referrer guarantee to third parties; where we want to keep attribution (OSM source), the header already limits Referer to origin-only [S11] — still no token.
- The share flow (`publicShareUrl`, `PlanView.tsx:133`) already uses a read-only token URL; this work item does not touch it. Nothing in the design introduces user PII into an external request.

---

## 5. Product / churn angle — trust vs. bounce

**Arguments for redirects:** The MVP's core promise is verifiability ("mỗi điểm được liên kết với nguồn thông tin thực tế"). A plan is more credible when the user can confirm a café exists on Google Maps, read the OSM entry, or see real TikTok clips. Redirect = trust and reduces support load.

**Arguments against:** Every new tab is a chance to lose the reading session. A link farm of 5 anchors per slot dilutes attention and reads as ad-like. The embedded Leaflet map + description already cover "where/what" without leaving.

**Recommendation — the right ratio:**
- **2 primary actions max** per slot: `Xem trên Google Maps` + `Chỉ đường`. These are the two actions with the highest intent-to-value ratio (verify-and-navigate).
- `TikTok` only as a *single* optional social link, only if the format checks out at implementation (§3.3); treat it as a growth experiment, wrapped in a known-good referrer policy.
- Keep `Nguồn` (it is the spec's provenance contract), but as the quietest label.
- **Never** auto-open links, show modals "redirecting…", or prepend tracking shorteners. Google's own guidance for Maps URLs is to give the destination directly [S1].
- Measure later, not now: there is no analytics surface in the MVP; a client-side fire-and-forget ping route (`/api/plans/{token}/outbound?target=maps`) is a sensible Tier-2 addition but is *tracking*, so it must be a plan-isolated, non-PII event and is out of scope for this lane unless requested.
- Guardrail against churn: the itinerary **panel remains open behind the new tab** (target=_blank), so the plan is never lost; Leaflet map stays embedded as the on-page "map" answer to reduce the need to leave.

---

## 6. Categorization & tiered plan

| # | Finding | Severity | Tier |
|---|---|---|---|
| F1 | No Google Maps/Search or TikTok redirect surface anywhere; map popups linkless | **High** (core MVP promo/provenance value missing) | Tier 1 |
| F2 | `nguon_url` rendered unfiltered (no https allowlist client-side); rel only `noreferrer` | **Medium** (low real risk today; hygiene + consistency) | Tier 1 |
| F3 | Slot lacks `khu_vuc`/`address` → Google place card falls back to coords-only pin | **Medium** (degrades card UX; not blocking — coords-link works) | Tier 2 |
| F4 | `website`/`phone` data dropped at load; no wikipedia/wikidata capture | **Medium** (Lane 3 remit; would enrich "Nguồn" later) | Tier 2 |
| F5 | TikTok `?q=` format undocumented by TikTok | **Low** (reverse-engineered confirm-at-impl item, §3.3) | Tier 2 |
| F6 | Churn risk of over-linking (reduces reading session) | **Low** if the §5 ratio (2 primaries max) is followed | Tier 1 (design baked in) |
| F7 | New slot-link clickability depends on `.slot-actions` / opt-in CSS (globals.css:26,65) | **Note** (implementation gotcha) | Tier 0 (as design note) |
| F8 | No token/PII leak path exists today (Referrer-Policy strips path) — preserve invariant | **Note / Blocker-guard** (never reintroduce) | Tier 0 (constraint) |
| F9 | Ambiguity coords-vs-name card UX (name match for generic POIs) | **Note** (documented decision: coords-first at MVP) | Tier 2 |

**Proposed sequencing:**
- **Tier 1 (this sprint):** `frontend/lib/external-links.ts` builders (§4.2); `Outbound` anchor with https allowlist + `noopener noreferrer`; slot action row = Google Maps + Chỉ đường (+ keep Nguồn, upgrade rel) inside `.slot-actions`; map popup links (sanitized); i18n keys ×19. Verify TikTok link by hand once (shift it to Tier 2 if it misbehaves → ship without).
- **Tier 2:** `khu_vuc`/`address` through slot payload (sync Lane 3) and switch card builder to name+area; optional TikTok link behind feature flag; optional non-PII outbound event ping.
- **Tier 3:** wiki/wikidata "Nguồn" variants and `website` link when Lane 3 enriches the import; `udm=14` only if we ever need AI-free search results (undocumented — confirm).

---

## Sources

- S1 Google Maps URLs guide (official) — https://developers.google.com/maps/documentation/urls/get-started (api=1 required; query: name/address/coords, %2C encoding, 2,048-char limit; query_place_id; directions origin/destination; utm guidance)
- S2 GoToAppleMaps "Google Maps URL Formats — Every Parameter Explained (2026)" — https://gotoapplemaps.com/guides/google-maps-url-formats-explained/ (search/dir/coordinate formats, place IDs, cid)
- S3 Olostep "Google Search URL Parameters: Complete 2026 Reference" — https://www.olostep.com/blog/google-search-url-parameters (q documented/stable; hl/gl; udm=14 reverse-engineered)
- S4 Bright Data + SerpApi Google Search parameter rundowns (2026) — https://brightdata.com/blog/web-data/google-search-url-parameters ; https://serpapi.com/blog/google-search-parameters
- S5 TikTok official search lander "Find '' on TikTok" — https://www.tiktok.com/search
- S8 SocialKit TikTok Search (2026) — exact `https://www.tiktok.com/search?q=funny+cats` example — https://www.socialkit.dev/tiktok-apis/search (and docs.socialkit.dev tiktok-search-api)
- S9 Apify TikTok-search scrapers accept `www.tiktok.com/search?q=` as startUrls — https://apify.com/epctex/tiktok-search-scraper
- S10 TikTok deep-link guides (app hand-off / web fallback) — https://u2l.ai/blog/how-to-create-tiktok-deep-link ; https://blog.linko.me/tiktok-deep-link/
- S11 MDN Referrer-Policy — `strict-origin-when-cross-origin` sends origin-only cross-origin, drops on downgrade — https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy
- S6 MDN rel=noopener ("target=_blank implies noopener"; noopener vs noreferrer) — https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/rel/noopener
- S7 OWASP Reverse Tabnabbing (WSTG-CLNT-14) — `rel="noopener noreferrer"` remediation; fixed in modern browsers — https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client-side_Testing/14-Testing_for_Reverse_Tabnabbing and https://owasp.org/www-community/attacks/Reverse_Tabnabbing
- S12 Legacy `maps.google.com/?q=lat,lng` formats — StackOverflow/industry-documented; pre-dates api=1 (not recommended)
- S13 Google official search-refine help (operators/URLs) — https://support.google.com/websearch/answer/2466433

**Ground-truth tally:** externally verified: 10 (S1–S11 core claims: Maps api=1 & query/dir formats, coords encoding, strict-origin ref policy, noopener/noreferrer rules, OSM source_url provenance from repo data, dataset coverage 3508/3508). Reverse-engineered / flagged unverified at implementation: 2 (TikTok `?q=` param S5/S8/S9; Google `udm=14`). Model judgment / design opinion: 3 (churn ratio §5, coords-vs-name card decision §4.2, tiering §6).

---

## Executive summary (lane 04)

The plan page currently has almost no outbound navigation surface. Slots render a single "Nguồn" anchor (`PlanView.tsx:235`) only when `nguon_url` is set — 100% of the 3,508-POI OSM catalogue has one (an OpenStreetMap permalink), but curated/demo places have none — and the Leaflet map markers (`MapView.tsx:41-45`) expose zero links. Verified ground truth for 2026: Google Maps place/directions links need the official `https://www.google.com/maps/search/?api=1&query=…` (coordinates `%2C`-encoded, `api=1` mandatory) and `…/maps/dir/?api=1&destination=lat%2Clng` (origin defaults to user location); Google Search is `?q=…&hl/gl`; TikTok search is `tiktok.com/search?q=…` but is **not officially documented — confirm at implementation**. Anchor safety is well settled (MDN + OWASP WSTG-CLNT-14): `target="_blank"` needs `rel="noopener noreferrer"`. The app is already safe on the PII vector: the global `strict-origin-when-cross-origin` Referrer-Policy strips the URL path (where the share token lives), and CSP's `default-src 'self'` does not block anchor navigation, so no header changes are required. Design: a deterministic client-side URL-builder module (never LLM-fabricated links, HTTPS-only allowlist mirroring `pdf_export.py`), two per-slot actions — "Xem trên Google Maps" (coords-first pin) and "Chỉ đường" — plus optionally TikTok and the existing Nguồn, placed inside `.slot-actions` so they survive the full-card `.slot-select` pointer-events trap, with the same actions sanitized into map popups. Churn-wise: stop at two primary actions (a link farm hurts retention); keep the tab-based flow so the itinerary is never lost. Highest severity: the map popups are linkless and the source anchor lacks a scheme allowlist; biggest open question is the TikTok URL format.

## Top 5 most concerning findings

1. **Map popups have no external links** (MapView.tsx:41-45) — on mobile, the map *is* the navigation moment, and the MVP ships without a "open in Maps" affordance there.
2. **`nguon_url` is rendered with no client-side https allowlist** (`rel="noreferrer"` only) — low exploitability today, but a single malformed DB row would render a bad href; the PDF path already guards this (pdf_export.py:130) and the plan view should too.
3. **TikTok search URL is undocumented by TikTok** — `https://www.tiktok.com/search?q=…` appears in 2026 third-party tooling but is reverse-engineered; if it regresses we'd ship a dead link, so it must be hand-verified at implementation (or gated).
4. **Data dropped in transit:** `address`, `website`, `phone` exist in places.json (≈7.7%/15.5% coverage) but die in `data.py:97-113`; without `khu_vuc`/`address` on the slot, the Google *place card* degrades to a coordinates-only pin (documented behavior, S1).
5. **Click-surface CSS trap:** any new slot links that are not inside `.slot-actions` (or given the `.icon-action`/`.source` opt-ins) are unclickable because `.slot-select` covers the card (`globals.css:26`) — a guaranteed implementation bug if missed.

## Confidence & tally

**Confidence: 7/10.** The design rests on the two most stable, officially documented URL families (Google Maps `api=1`; Google Search `q`) with 2026 corroboration, plus well-established security guidance (MDN/OWASP). It drops to ~6 on the TikTok leg (undocumented format) and the coords-vs-name card trade-off is a genuine UX judgment call I could not resolve from documentation alone. Ground-truth tally: **10 externally verified** (Maps api=1/query/dir + %2C encoding; search q stable; strict-origin referrer semantics; noopener/noreferrer rules; OSM source_url provenance incl. 3508/3508 coverage and 0 wikipedia tags) vs **2 unverified-flagged** (TikTok `?q=`; Google `udm=14`) vs **3 model-judgment items** (churn ratio, coords-first decision, tier ordering). Not counted toward confidence: no live click-through or A/B data exists in-repo to validate the churn hypothesis.