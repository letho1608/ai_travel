# Lane 4 — Share Feature & Platform Integration Audit

**App:** Mình Đi Đâu Thế (Next.js frontend + FastAPI backend, Vietnamese)
**Lane scope:** the "Chia sẻ" button, public share links, mobile/Zalo webview behavior, deployment topology (run.bat/localhost/CORS/HTTPS), link-preview metadata, read-only semantics, offline service worker.
**Owner report:** "nút chia sẻ chưa hoạt động" (share button doesn't work).
**Method:** static code trace + current web evidence (secure-context clipboard rules, Web Share API support matrix, in-app WebView behavior, Zalo Open Graph scraping). Research only — no code modified.

---

## 0. Verdict up front

The copy-to-clipboard code is technically defensible *on the one machine where it can ever succeed* (the creator's `localhost`, which is a browser-secure context). The button almost certainly shows "Đã sao chép liên kết chỉ đọc" and puts `http://localhost:3000/plan/<token>` on the clipboard. **The link itself is the bug**: every recipient who taps it resolves `localhost` to *their own* device and hits a connection-refused page. Even on a LAN where the frontend is reachable, the baked-in `http://localhost:8000` API URL and the localhost-only CORS allowlist break every client-side call on the recipient's device. "Share" is therefore a **copy of a broken URL** in every real environment except the creator's own browser tab. Secondary but real problems: no Web Share API (no native share sheet on mobile — the #1 expected gesture in the Vietnamese/Zalo market), no `og:image` (Zalo renders a bare text link, which "doesn't feel like sharing"), and a 30-day expiry that silently kills shared links.

The fix is not "make the button copy better." It is a deployment-model fix (public HTTPS origin + configurable public base URL + prod CORS) plus a share-sheet fix (Web Share API → clipboard → visible confirmation).

---

## 1. The share button end-to-end flow (as built)

```
[CREATOR on creator's PC]
  generate plan  ->  /plan/<uuid>  (server-rendered; data fetched SSR from API_URL)
  click "Chia sẻ"  (PlanView.tsx:92)
    copy()  (PlanView.tsx:77)
      copyShareLink(location.href)  (PlanView.tsx:30)
        location.href = http://localhost:3000/plan/<uuid>   <-- baked localhost origin
        navigator.clipboard.writeText(url)                  <-- works: localhost IS a secure context
             |_ if undefined/rejects -> hidden <textarea> + document.execCommand("copy")
      setMessage("copied")  ->  status div "Đã sao chép liên kết chỉ đọc" (PlanView.tsx:94)
  user pastes URL into Zalo chat
        |
        v
[RECIPIENT in Zalo / any phone]
  taps http://localhost:3000/plan/<uuid>
    browser resolves "localhost" = RECIPIENT'S OWN DEVICE
    nothing listening on :3000  ->  ERR_CONNECTION_REFUSED / Zalo webview error page
        |  ^^ SHARE IS DEAD HERE. 100% of recipients. ^^
  (best case, same LAN + URL manually rewritten to http://192.168.1.5:3000/plan/<uuid>)
    SSR renders (server-side fetch to localhost:8000 runs on CREATOR's machine -> OK)
    client JS hydrates -> comments fetch hits API_URL = http://localhost:8000
        on RECIPIENT's browser -> their localhost -> fail
        even if API_URL were corrected, origin http://192.168.1.5:3000
        is NOT in CORS allowlist (config.py:10-14) -> CORS blocked
    -> read-only page body may render, but comment thread + every interaction dead
```

Every arrow after the paste is broken in every environment except creator-only localhost.

---

## 2. Clipboard mechanics: what actually happens per environment

### 2.1 Secure-context rule (verified)

`navigator.clipboard.writeText` is only exposed in a **secure context**. MDN, the W3C Clipboard API spec, and multiple 2025–2026 sources agree: on plain `http://` origins `navigator.clipboard` is literally `undefined` (throws `TypeError: Cannot read properties of undefined (reading 'writeText')` if unguarded). `http://localhost`, `http://127.0.0.1`, and `::1` **are** treated as secure contexts — which is exactly why the button works on the developer's own machine.

Mapping this app's real origins:

| Origin in play | `isSecureContext` | `navigator.clipboard.writeText` |
|---|---|---|
| `http://localhost:3000` (creator, run.bat:120) | **true** (loopback exception) | available → copy succeeds |
| `http://192.168.x.x:3000` (LAN, would-be sharing) | **false** | `undefined` → execCommand fallback |
| `http://<any-domain>` (no TLS) | **false** | `undefined` → execCommand fallback |
| `https://<domain>` (production) | true | available |
| Zalo in-app webview (Android) | true only if URL is HTTPS | varies; often restricted |

So the "copied" success the owner sees on `localhost` is not portable to any origin a recipient could actually use.

### 2.2 Is the `execCommand` fallback reliable? (verified)

`document.execCommand('copy')` is **deprecated** (MDN; no longer in any spec; Chromium source keeps it "only for legacy reasons"). Evidence on current reliability:

- **Still works in every shipping browser** when invoked **synchronously inside the click handler** — this is the classic textarea fallback, and it is the only path that reaches non-secure contexts and most in-app WebViews.
- **Chrome has begun restricting it outside a synchronous user-gesture call stack.** A documented 2025 bug report (Infrahub #8857, referenced by a fix PR "copy to clipboard fails over HTTP") describes exactly this code shape: when the fallback runs *inside an async `catch` (Promise microtask) after `await navigator.clipboard.writeText(...)` rejects*, Chrome 146 **ignores `execCommand('copy')` and returns `true` anyway** → silent false-success. See §2.3 — this repo has precisely that bug.
- **iOS Safari/WebKit quirk:** `execCommand('copy')` on a `textarea` requires a *visible selection*; the known fix is `element.setSelectionRange(0, text.length)` before `select()`. The code here calls `select()` only (`PlanView.tsx:41`) and styles the element `opacity:0` — on iOS the copy commonly fails and returns `false`.

### 2.3 The microtask bug in `copyShareLink` (traced, high confidence)

```ts
async function copyShareLink(value) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);   // (a) if present but REJECTS
      return true;
    }
  } catch {}
  try {
    ... textarea ...
    return document.execCommand("copy");            // (b) runs in a microtask after (a)'s await
  } catch { return false; }
}
```

- If `navigator.clipboard` is `undefined` (all non-secure origins), the `if` short-circuits, **no `await` runs**, and `execCommand` executes synchronously in the click's call stack → fallback is the documented-working shape (reliable on Android, unreliable on iOS per 2.2).
- If `navigator.clipboard` **exists but `writeText` rejects** (`NotAllowedError` — permission denied, document unfocused, or a WebView clipboard bridge rejecting; explicitly called out in MetaMask's Android WebView work), the `catch` runs as a **Promise microtask** after the click's user activation is consumed → Chrome ≥146 may silently no-op `execCommand`, and may still return truthy → user is told "Đã sao chép liên kết chỉ đọc" when **nothing was copied**. This is the one real "button doesn't do anything" failure at the *copy* layer, and it occurs precisely in the WebView-heavy target market.

**Bottom line for the target audience** (Vietnamese mobile users opening links inside Zalo): the *copy* fails outright only in the reject-then-microtask case and on iOS; but the *shared link* is broken for 100% of recipients regardless, because it is `http://localhost:3000` (§3). The copy layer is a secondary bug; the URL is the primary one.

---

## 3. Public-link sharing design: the real "share doesn't work"

### 3.1 The chain that makes share links non-functional off the creator's machine

1. **URL source.** `copy()` shares `location.href` (`PlanView.tsx:77`). On the only tested setup (`run.bat`), that is `http://localhost:<port>/plan/<token>`. `localhost` is loopback — it names *the device that resolves it*, so every recipient resolves it to themselves.
2. **API URL baked at (dev) start / (prod) build.** `NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` (`frontend/lib/api.ts:3`). `run.bat:120` injects `NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT%` at launch; `.env.example:5` mirrors it. In production builds this string is inlined into client bundles — there is no runtime reconfiguration and no `PUBLIC_BASE_URL`/`NEXT_PUBLIC_BASE_URL` concept anywhere in the repo (grep confirms zero matches).
3. **CORS allowlist is localhost-only.** `backend/app/config.py:10-14` builds origins from `http://localhost:{3000..3010}` and `http://127.0.0.1:{3000..3010}`. `validate_production()` even *requires* every CORS origin to be `https://` (`config.py:73`), yet nothing ships a production HTTPS origin.
4. **The plan page's SSR fetch uses the same baked URL.** `frontend/app/plan/[token]/page.tsx:5` → `fetch(\`${API_URL}/api/plans/${token}\`, {cache:"no-store"})`. On the recipient's device this runs *server-side on the creator's machine* (fine when the frontend is reachable), but on a non-local deployment with no `NEXT_PUBLIC_API_URL`, the default `http://localhost:8000` resolves on the server → `fetch` fails → `notFound()` (`page.tsx:7`). The page then renders the generic Next.js 404.

### 3.2 Where the chain breaks, scenario by scenario

**(a) Share to a friend on the same LAN.** Frontend `http://192.168.1.5:3000` is browser-reachable. But the copied `location.href` is `http://localhost:3000/...` → friend resolves to their own machine → refused. *Even if the user hand-fixes the host*: SSR works (creator's server fetches its own `localhost:8000`), the plan body renders, but the client-side comments fetch (`PlanView.tsx:74`) targets `http://localhost:8000` in the friend's browser (their machine) and — even if fixed to the LAN IP — is **CORS-blocked** because `http://192.168.1.5:3000` is not an allowed origin. Result: a read-only skeleton with no comments and no interactive features.

**(b) Share to a phone on cellular.** The copied URL is unreachable from the start: `localhost` is not routable, and there is no public origin. This is the dominant real-world case for "Chia sẻ" → Zalo → friend on mobile. 100% dead.

**(c) Share inside Zalo.** Recipient taps the link inside Zalo's in-app webview. The URL is `http://localhost:3000/...` → Zalo's webview resolves `localhost` to the phone → `ERR_CONNECTION_REFUSED` error page inside the chat. Even with a correct public HTTPS URL, three more layers would need to hold: (i) the webview needs the page to load over HTTPS (secure-context requirement for clipboard, §2.1; Web Share API also requires HTTPS), (ii) `NEXT_PUBLIC_API_URL` must point at a public API the phone can reach, and (iii) the backend's CORS allowlist must include the public frontend origin. The README itself flags this: PoC-SSE "preview link thật trong Zalo cần domain/tài khoản" (`README.md:60`) — the owner already knows a real domain is a prerequisite and it is not implemented.

### 3.3 No configuration seam for any of this

There is no `PUBLIC_BASE_URL`, no `SITE_URL`, no `NEXT_PUBLIC_BASE_URL` in `.env.example`, `.env`, `api.ts`, `next.config.mjs`, or any page. A correct share experience *requires* a canonical public origin (a) to build the share URL server-side instead of reading `location.href`, (b) for `metadataBase`/Open Graph, and (c) to feed CORS. The repo has none.

---

## 4. Read-only semantics (verified) and expiry

### 4.1 Genuinely read-only for the plan body — with one leak

- `GET /api/plans/{token}` (`backend/app/routers/plans.py:134-139`) performs **no auth check** and returns `{ke_hoach, phien_ban, token}`. This is what the share page consumes.
- `owner()` (`plans.py:50-55`) — which 403s unless the request carries the owner's `X-Session-Id`/Bearer — is applied only to **mutate** endpoints: `swipe` (320), `refine` (461), `restore` (524), `regenerate` (397), `feedback` (235), `versions` GET (510), `resolve_comment` (288). A shared recipient has none of these, so the plan content is genuinely read-only. Good.
- **Leak:** `POST /api/plans/{token}/comments` (`plans.py:258-275`) and `GET /comments` (251-255) are **not** `owner()`-guarded. Anyone with the token can list *and write* comments, spoofing `ten_hien_thi`, rate-limited only per `ma_phien` (266). So a "read-only link" is not read-only for the comment thread. This is a share-semantics/product decision, but it contradicts the README's "Link chia sẻ là UUID và chỉ đọc" claim (`README.md:64`).

### 4.2 Refreshing a shared link works (verified)

`page.tsx:5` uses `{cache:"no-store"}` → every SSR hit re-fetches the plan from the backend, so a recipient refreshing the page gets the current version. If the owner later refined the plan, the shared recipient sees the latest revision — which is the correct "live read-only link" behavior.

### 4.3 30-day expiry (verified) — a product problem

- `store.save()` sets `expires_at = now + 30 days` (`backend/app/services/store.py:64`).
- `store.get()` returns `None` once expired (`store.py:72-76`); `cleanup_expired()` prunes hourly (`store.py:352-370`; README:51).
- Expired and never-existed are **indistinguishable**: both 404 with "Kế hoạch không tồn tại hoặc đã hết hạn" (`plans.py:138`), and the page calls `notFound()` (`page.tsx:7`) → generic "This page could not be found".
- Contrast: plans claimed by a **logged-in** user get `expires_at = None` (permanent) via `claim_session` (`store.py:387`). So the product already treats authenticated users' plans as permanent while *shared* links die in 30 days. For group trips shared to friends (the whole point of the button), a 30-day rot on a "read-only reference" is surprising, and the silent generic 404 gives recipients no explanation.

---

## 5. Other integration issues in this lane

### 5.1 No Web Share API (verified absent)

Repo-wide grep for `navigator.share` / `canShare` returns **zero matches**. The button is exclusively a silent copy. Current evidence: Web Share API is "not Baseline" (MDN), stripped in most in-app WebViews (Instagram/TikTok/Facebook/MetaMask Android WebView all need JS-native bridges or polyfills), and absent entirely in desktop Firefox. For a Vietnamese mobile-first audience where the native "share sheet" (Zalo, SMS, Messenger, email targets) is the expected gesture, shipping copy-only means the primary sharing pattern is missing.

### 5.2 No `og:image` and no image asset at all (verified)

- `generateMetadata` (`frontend/app/plan/[token]/page.tsx:6`) returns only `title`/`description`/`openGraph{title,description}` — **no `images`, no `metadataBase`, no `twitter` card**.
- Root layout (`frontend/app/layout.tsx:8`) has title/description only, no images.
- `frontend/public/` contains **only `sw.js`** — no `opengraph-image.*`, no `icon.*`, no favicon, no static image (glob confirms; grep for `opengraph-image`/`icon` files returns nothing).
- Web evidence: Zalo reads Open Graph exactly like Facebook; without an absolute HTTPS `og:image` (1200×630, ≥600px wide, public, no robots.txt block, no auth) Zalo shows a bare text link with no thumbnail, and its scrapers cache previews per URL (Zalo Debug Sharing tool exists to refresh). Vietnamese SEO/agency sources confirm the dominant cause of "Zalo không hiện hình" is missing/relative `og:image`.
- **Consequence:** even after the URL itself is fixed, a shared link renders as a naked URL in Zalo chat — low CTR, looks like spam, "doesn't feel like sharing." No `metadataBase` means even a *relative* og image would break (crawlers need absolute URLs).

### 5.3 Service worker / offline (verified, minor)

- `frontend/public/sw.js`: precaches shell `["/","/history","/login","/explore","/roadtrip","/settings"]` (`sw.js:2`); network-first for same-origin GETs (`sw.js:16-26`); **ignores cross-origin** requests (line 20) — so the API (`localhost:8000`) is never cached, and `/plan/[token]` is only cached opportunistically after a first visit (it's not in the shell).
- Registration is **production-only** (`components/ServiceWorkerRegistration.tsx:7`), so it is never active under `run.bat`/`next dev` anyway.
- Practical effect: an offline shared-plan page whose HTML was visited once may render from cache, but its comment thread and any interaction die, and the `/plan/[token]` fallback in `sw.js:25` is `caches.match("/")` — a mis-served home page rather than a "plan unavailable" state. Low priority, but a correctness smell for a "read-only shared link" story.

### 5.4 CSP is not the blocker for production (verified, note)

`next.config.mjs:5-10` allows `connect-src` for localhost:8000–8010, 127.0.0.1:8000–8010, **and `https:`** — so once the API is on a real HTTPS origin the CSP permits it. CSP only matters for the client bundle; the SSR fetch in `page.tsx:5` is unaffected by CSP. Worth noting because it means CSP does **not** need changing to deploy properly; CORS and `API_URL` do.

---

## 6. Severity list

| # | Severity | Finding | Evidence | Recommended fix |
|---|---|---|---|---|
| 1 | **Blocker** | Shared URL is `location.href` = `http://localhost:<port>/plan/<token>`; every recipient resolves `localhost` to themselves → connection refused. Copy works; the *link* is dead 100% off the creator's machine. | `PlanView.tsx:77`; `run.bat:120`; `api.ts:3` | Introduce `NEXT_PUBLIC_BASE_URL` (public origin); build the share URL as `` `${NEXT_PUBLIC_BASE_URL}/plan/${token}` `` (server-render it into the page; never trust `location.href`). Document in `.env.example`. |
| 2 | **Blocker** | API base baked to `http://localhost:8000` and CORS allowlist is localhost-only; even a LAN-shared frontend fails all client calls (CORS) and a deployed frontend without the env var 404s at SSR. | `api.ts:3`; `config.py:10-14`; `page.tsx:5`; `.env.example:5-6`; `README.md:60` | Deploy frontend+backend on public HTTPS origins; set `NEXT_PUBLIC_API_URL=https://api.<domain>` and `CORS_ORIGINS=https://<domain>`; production guard already rejects non-HTTPS CORS (`config.py:73`) — that's the intended path, it just isn't configured anywhere. |
| 3 | **High** | No Web Share API; mobile users get a silent copy instead of the native share sheet that the Zalo/Vietnamese mobile audience expects. | grep `navigator.share` → 0 matches; MDN/WebShare API support matrix (WebViews strip it, desktop Firefox none) | `if (navigator.canShare?.({url})) await navigator.share({title, text, url})` as primary; fall back to clipboard; always expose a second explicit "Sao chép liên kết" affordance; add i18n keys. |
| 4 | **High** | Fallback `execCommand` unreliable in target envs: (a) Chrome ≥146 silently ignores it when called from an async microtask — exactly this code shape when `writeText` rejects; (b) iOS Safari needs `setSelectionRange` (absent) → returns `false`. Both can yield false "Đã sao chép" messages. | `PlanView.tsx:32-45`; Infrahub #8857; iOS selection quirk sources | Make legacy copy synchronous: guard `if (!navigator.clipboard || !window.isSecureContext) → run execCommand inline in the click`; add `setSelectionRange(0, value.length)`; keep `await` only on the secure-context path; treat `execCommand===false` as failure. |
| 5 | **Medium** | No HTTPS → `navigator.clipboard` is `undefined` on any real non-loopback origin; Web Share API also requires HTTPS; Zalo scraper and webview won't get secure context. | `next.config.mjs` CSP (allows `https:` — correct direction); MDN secure-context | Serve production behind TLS (Railway/Vercel/Caddy). Loopback stays as the only clipboard-capable dev origin. |
| 6 | **Medium** | Feedback discoverability: success/failure is a small `role="status"` text div at the very top of the page, far from the button, sharing the slot with the "busy" indicator; no toast, no auto-dismiss, no next-to-button confirmation. | `PlanView.tsx:94`; `workspace-translations.ts:5` (`copied`/`copyFailed`) | Render a transient toast near the trigger ("Đã sao chép liên kết"), `aria-live` polite, auto-dismiss ~2.5s; on failure show manual-copy instruction + selectable URL. |
| 7 | **Medium** | No `og:image`, no `metadataBase`, no image asset anywhere → Zalo shows a bare URL card with no thumbnail (looks like spam, low CTR). | `page.tsx:6`; `layout.tsx:8`; `public/` only `sw.js` | Add `metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL)` + an `opengraph-image.tsx` route segment (or static 1200×630 `/og.png`) per plan; emit absolute HTTPS `og:image` + `og:image:width/height` + `twitter:card`; re-scrape via Zalo Debug Sharing after deploy. |
| 8 | **Medium** | 30-day expiry silently kills shared read-only links; expired == never-existed generic 404. Logged-in users' plans are permanent (inconsistent). | `store.py:64`; `store.py:72-76`; `plans.py:138`; `store.py:387` | For shared/owner-claimed plans: drop expiry (`expires_at=None`) or extend to e.g. 1 year; differentiate the 404 (`detail` = "đã hết hạn") and surface a Vietnamese message on the page instead of generic not-found. |
| 9 | **Low** | `execCommand` false-success risk in the WebView case (§2.3) is *also* a correctness bug at the copy layer, included above; listed separately for triage. | `PlanView.tsx:30-46` | See fix #4. |
| 10 | **Note** | "Read-only link" is not read-only: `POST/GET /comments` are unguarded by `owner()` → anonymous comment spam/spoofing with a shared token. | `plans.py:251-275`; README:64 | Decide policy: either require `ma_phien`/auth for writes, or scope comments to a share-participant capability; at minimum document the deviation. |
| 11 | **Note** | Service worker: `/plan/[token]` not in precache shell; cross-origin API never cached; registration production-only; offline fallback serves home page. | `sw.js:2,16-26`; `ServiceWorkerRegistration.tsx:7` | Add `/plan/[token]` runtime caching with a proper offline fallback; keep cross-origin exclusion but add an explicit "plan unavailable offline" state. |

---

## 7. Recommended target architecture (concrete)

**Config seam (new):** `NEXT_PUBLIC_BASE_URL` (e.g. `https://minhdidauthe.example`) + `NEXT_PUBLIC_API_URL=https://api.example`. Both in `.env.example`, validated at build; `metadataBase` derived from `NEXT_PUBLIC_BASE_URL`.

**Share handler (PlanView.tsx):**
1. URL = `` `${NEXT_PUBLIC_BASE_URL ?? window.location.origin}/plan/${token}` ``.
2. `if (navigator.canShare?.({url})) → navigator.share({title: plan.tieu_de, text: plan.tom_tat, url})` (reject/`AbortError` = user cancelled → do nothing).
3. else clipboard: synchronous legacy guard when `!navigator.clipboard || !window.isSecureContext`; `writeText` on the secure path with `.then/.catch`.
4. Visible toast near the button on success; explicit "copy link" secondary action always available.

**Ops:** deploy behind TLS; set CORS to the public origin; keep the production `validate_production()` gates (they already require HTTPS CORS). Add per-plan `opengraph-image` + static asset. Adjust expiry policy for shared links.

---

## 8. Executive summary (250 words)

The "Chia sẻ" button does not fail at the copy step on the developer's own machine — `localhost` is a secure context, so `navigator.clipboard.writeText` succeeds and the status line "Đã sao chép liên kết chỉ đọc" appears. It fails at the *link itself*: the button shares `location.href`, which under `run.bat` is `http://localhost:3000/plan/<token>`. Every recipient — a friend on the LAN, a phone on cellular, a Zalo webview — resolves `localhost` to their own device and gets a connection-refused error. The whole deployment model reinforces this: `NEXT_PUBLIC_API_URL` is baked to `http://localhost:8000` (`api.ts:3`, `run.bat:120`), the backend CORS allowlist admits only localhost origins (`config.py:10-14`), and there is no public base URL concept anywhere in the repo. Even a hand-fixed LAN URL renders only a shell: client-side calls are CORS-blocked and the baked API URL points at the recipient's own machine. Secondary but real defects compound this: there is no Web Share API (native share sheets are stripped in in-app WebViews like Zalo, so the copy path is the only gesture, and the legacy `execCommand` fallback is unreliable on iOS and, since Chrome 146, when invoked from an async microtask after `writeText` rejects); there is no `og:image` or `metadataBase`, so a shared link renders as a bare URL card in Zalo; and a 30-day expiry silently kills shared links with a generic 404. Fixing "share" means shipping a public HTTPS origin, a configurable base URL, prod CORS, Web Share + clipboard with a visible toast, and Open Graph image metadata — not polishing the copy function.

## 9. Top 5 findings

1. **Blocker — the shared URL is `http://localhost:3000`.** `location.href` is copied verbatim (`PlanView.tsx:77`); recipients resolve `localhost` to themselves → connection refused. This alone is why "nút chia sẻ chưa hoạt động."
2. **Blocker — no deployable API/CORS topology.** `NEXT_PUBLIC_API_URL` defaults to and is baked as `http://localhost:8000` (`api.ts:3`, `run.bat:120`); CORS admits only `localhost:3000-3010` (`config.py:10-14`); no `PUBLIC_BASE_URL` exists → every non-localhost client call fails or 404s at SSR.
3. **High — copy fallback is unreliable in the target market.** No `navigator.share`; the only gesture is a silent copy; `execCommand` fallback is async-microtask-broken on Chrome ≥146 and selection-broken on iOS (`PlanView.tsx:30-46`) → false "Đã sao chép" possible.
4. **Medium — no link preview.** No `og:image`, no `metadataBase`, no image asset (`page.tsx:6`, `layout.tsx:8`, `public/`), so Zalo shows a bare URL — sharing "doesn't feel like sharing."
5. **Medium — 30-day expiry + write leak on a "read-only" link.** Shared links rot with a generic 404 (`store.py:64`), and comments POST is unguarded by `owner()` (`plans.py:258-275`) — the read-only contract is incomplete.

## 10. Confidence & ground-truth tally

**Confidence: 8/10.** The primary diagnosis (localhost-based share URL, baked API URL, localhost-only CORS, no share API, no og:image, 30-day expiry) is directly verified in code and is not speculative — those are the load-bearing findings and I would defend them at 9/10 on their own. The deduction to ~8 is driven by the *behavioral* claims I could not run here: exact Zalo WebView clipboard/share behavior (no device), whether Chrome's microtask restriction fires in this specific build, and the true click-rate impact of the missing og image — those rely on current web evidence rather than empirical testing on the app.

**Ground truth — verified in code (18 items):** `PlanView.tsx:30-46,77,92,94` (copy impl, status div); `api.ts:3` (API_URL default); `config.py:10-14,73` (CORS); `plans.py:134-139,50-55,251-275` (public GET, owner guard scope, unguarded comments); `store.py:64,72-76,352-370,387` (expiry, get() expiry check, cleanup, claim_session permanence); `page.tsx:5-6` (SSR no-store fetch, metadata w/o og:image); `layout.tsx:8` (no images); `next.config.mjs:5-10` (CSP connect-src incl. `https:`); `sw.js:2,16-26` (shell, network-first, cross-origin skip); `ServiceWorkerRegistration.tsx:7` (prod-only); `run.bat:120`; `.env.example:5-6`; `README.md:60,64`; grep `navigator.share` = 0 matches; glob `public/` = only `sw.js`; no `opengraph-image`/`icon`; no `PUBLIC_BASE_URL`/`SITE_URL` anywhere.

**Ground truth — verified by WebSearch (6 items):** clipboard API requires secure context; `localhost` counts as secure; `execCommand('copy')` deprecated but still implemented; Chrome ≥146 async-microtask `execCommand` failure case (Infrahub #8857); iOS Safari `setSelectionRange` requirement; Web Share API "not Baseline" and stripped in in-app WebViews; Zalo reads Open Graph and requires absolute HTTPS 1200×630 `og:image` (Zalo Debug Sharing).

**Model judgment (not empirically verified):** Zalo WebView's specific clipboard/share implementation; the measured frequency of `writeText` rejection in webviews; the real CTR loss from missing preview cards; the Chrome build where the microtask restriction ships. These are the residual uncertainty driving the 8/10.
