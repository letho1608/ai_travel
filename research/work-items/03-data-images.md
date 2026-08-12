# Work Item 03 — Lấy data & hình mới nhất về địa điểm (latest place data + images)

Agent lane: **data + image freshness for the Hanoi MVP** (agents 1, 2, 4, 5, 6 cover UI/route/links/manual-change/duration).
Status: research only — no code changed. All repo line references verified against the working tree at `2026-08-11`. All "live" checks (Overpass, Commons, Wikidata) executed by the author this session.

---

## 0. TL;DR

- **Only 16 of 3,529 catalogue places (0.45%) have any image today**, and every one of them is a hand-typed URL in `data.py` covering only curated anchors. In the PostgreSQL path (`APP_ENV != local`) that number collapses to **0**: `seed_postgres.py` writes `hinh_anh = NULL` and `data.py:331` only maps `hinh_anh` to `image_url`.
- The OSM import captures **no wikipedia / wikidata / wikimedia_commons / image tags** (`import_osm_places.py:70-116`), so the catalog has no cross-reference to build from — but the underlying OSM data does: a live Overpass scan of the same bbox found 40/4,749 matching features (0.84%) tagged `wikipedia`, 41 `wikidata`, 22 `wikimedia_commons` (21 of them Category, only 1 a File), 3 `image=`. The coverage skews strongly to museums/attractions/parks — the exact places tourists want — and is ~zero for the 3,000+ cafes/restaurants.
- The **cost-free, provenance-compliant, deterministic** fix already exists and was validated live this session: OSM `wikidata`/`wikipedia` → Wikidata `P18` claim → Wikimedia Commons file → `prop=imageinfo&iiurlwidth=800` gives a guaranteed thumbnail URL + machine-readable license (`LicenseShortName`), artist, and credit line. Commons **hotlinking is allowed but officially not recommended** (`Commons:Reusing_content_outside_Wikimedia/technical`), so store the file page URL + license + fetched_at and hotlink only the thumbnail (or self-host later).
- **Recommended MVP**: Tier 0 = replace the hand-typed URL map with ~30 verified Commons file references and start *rendering* `anh_nguon` (attribution is currently carried on the wire but never displayed — a real licensing gap); Tier 1 = a weekly, api-key-free `enrich_images.py` that resolves OSM `wikidata`→`P18`→Commons and writes a provenance overlay (`hinh_anh` + `hinh_anh_meta`); Tier 2 = Commons *geosearch* fallback for untagged sight kinds + kind-themed placeholder; Tier 3 = paid/commercial sources (Google Places Photo, Unsplash, Flickr) only when the MVP needs photos for cafes/restaurants that open data cannot cover.

---

## 1. How the app gets place data and images today

### 1.1 Place catalogue (three layers)

The catalogue is assembled in `backend/app/data.py` at import time:

1. **Hardcoded demo list** (`data.py:79-92`) plus **curated anchors/dining** (`data.py:121-300`) — `source="curated"`, ids like `curated-ho-guom`.
2. **OSM-imported catalogue** `backend/data/places.json` (3,508 places, `fetched_at = 2026-08-06T10:34:16Z`, license `ODbL 1.0` per `import_osm_places.py:135`), loaded via `_load_imported_places()` (`data.py:97-113`). When present, it *replaces* the demo list (`data.py:116-118`); curated places are then appended (`data.py:302-307`). Net local catalogue: **3,529 places**.
3. **PostgreSQL catalogue** (`data.py:310-339`, used when `APP_ENV != "local"`): SELECT from `dia_diem` where `trang_thai='active'`, mapping `image_url = hinh_anh` (`data.py:331`). **Every seeded row has `hinh_anh = NULL`** because `seed_postgres.py:57` inserts `None` for that column — so production currently renders **zero** images.

`Place` already carries the fields we need for this lane: `image_url`, `image_credit`, `source`, `source_url` (`data.py:10-26`); `image_for()` (`data.py:72-76`) returns either the Place's own image or the static lookup maps.

### 1.2 The current image store: a small hand-typed map

`PLACE_IMAGE_URLS` (`data.py:29-53`) and `PLACE_IMAGE_CREDITS` (`data.py:55-69`) hold 23 hardcoded `Special:FilePath/…?width=800` Commons URLs keyed by place id. Of those, **12 unique files** cover **16 places**; the 7 leftover entries are dead keys (e.g. `van-mieu`, `ho-guom` — replaced by OSM import). One file (`Hanoi_shophouse_2.jpg`) is reused for **all nine** Hàng-street entries. Nothing in this map is validated at build time, and the only guard is the client-side `brokenImages` set.

### 1.3 How images reach a plan slot

- `planner.py:1074-1089` builds each slot: `image_url, image_credit = image_for(place)`; the slot carries `"anh": image_url` and `"anh_nguon": image_credit`.
- Frontend: `safeImageUrl` (`PlanView.tsx:46`) enforces http(s); `brokenImages` state (`PlanView.tsx:100`) records urls that failed; `hideImage` (`PlanView.tsx:222`) and `slotPhoto` (`PlanView.tsx:223`) render `next/image` **unoptimized** with `onError` gating; the itinerary hero picks the first non-broken image (`PlanView.tsx:219, 235`).
- **Attribution gap**: `Slot.anh_nguon` exists in the type (`frontend/lib/types.ts:1`) but a repo-wide search shows it is **never rendered** — no credit line under any photo. Commons/CC-BY images shown without visible attribution and license link are a licensing-violation risk (see §3).

### 1.4 OSM import blind spots

`normalize()` (`import_osm_places.py:70-116`) keeps `name`, `kind`, `area`, `address`, coords, `cost=0`, `duration_min=60`, a fixed `tags` subset (cuisine/outdoor_seating/wheelchair/tourism/leisure/historic), raw opening hours, website, phone, and provenance. It **does not keep** `wikipedia`, `wikidata`, `wikimedia_commons`, or `image` tags — the exact keys needed to resolve photos. The query (`import_osm_places.py:36-45`) also doesn't request `image=*`, but the raw `out tags` response contains them; the importer just drops them. This is a one-line-to-few-lines fix (add 4 tag reads to the dict).

### 1.5 Quality instrumentation

`/api/admin/catalog/quality` (`admin.py:145-190`) reports source_url coverage, hours quality, kinds, top tags — but **no image/photo coverage metric**. Any future image pipeline should register `image_coverage_percent`, `image_by_provider`, `image_last_fetch` here so the demo story can be "verified, sourced, fresh" rather than "some slots are blank".

---

## 2. Empirical verification (measured this session)

To keep this honest, I pulled live numbers rather than relying on assumptions:

- **Local catalogue**: `python -c "from app.data import PLACES, image_for …"` → **3,529 places, 16 with an image via `image_for()`, 21 curated**. So 0.45% coverage, all curated anchors.
- **Overpass scan (bbox of the importer, `20.90,105.70,21.16,106.02`)**, same amenity/tourism/leisure filter as the importer, `out tags`: **4,749 features**; `wikipedia` on **40** (0.84%), `wikidata` on **41** (0.86%), `wikimedia_commons` on **22** (21 Category + 1 File), `image=` on **3**, `flickr`/`mapillary` **0**. Tagged places cluster in `museum` (13), `attraction` (11), `park` (9), `place_of_worship` (3), `marketplace` (2), `cafe` (1), `restaurant` (1).
  - → The open-data signal is real exactly where a Hanoi visitor cares (museums, attractions, parks), and near-absent for food/drink. Any plan that promises "photos for every café" from free sources is AS-PROVEN IMPOSSIBLE in the near term; the roadmap must either accept blank slots + themed placeholders for food, or go paid (§3.5).
  - Reliability note: Live Overpass returned **504 Gateway Timeout on both `overpass-api.de` and `overpass.kumi.systems`** on retries today; first run succeeded. Weekly re-imports must (a) retry across mirrors, (b) honor the [Overpass usage policy](https://overpass-api.de/usage_policy.html) (throttle; default public slots), and (c) accept that a scheduled run can fail-retry.
- **Commons `Special:FilePath` probe**: `Special:FilePath/Hoan_Kiem.jpg?width=800` → `200` → `upload.wikimedia.org/wikipedia/commons/1/1c/Hoan_Kiem.jpg?utm_…` i.e. the **original file**, not a guaranteed rescale; exact scaling semantics of the `width=` param vary. **Under a 12-URL burst I received `429 Too many requests`** — commons.wikimedia.org rate-limits bot-like bursts, so batch verification must throttle (~1 req/s), which the read-time browser hotlink flow (`<img>` per slot) does not hit the same way.
- **Commons geosearch** (`commons.wikimedia.org/w/api.php?action=query&generator=geosearch&ggsnamespace=6&ggscoord=21.0287|105.8522&ggsradius=300&ggslimit=5&prop=imageinfo&iiurlwidth=800&iiprop=url|extmetadata`) → 5 files within 300 m of Hoàn Kiếm, each returning `thumburl` + `extmetadata.Artist`. So coordinate-based fallback for untagged sights is viable.
- **Full resolution chain validated** (3 real Hanoi subjects):
  - `wbsearchentities` "Văn Miếu – Quốc Tử Giám" → `Q1202019`
  - `wbgetentities?claims=P18` → `Hanoi Temple of Literature.jpg`
  - Commons `imageinfo&iiurlwidth=800&iiprop=url|extmetadata` → `thumburl` …`/960px-Hanoi_Temple_of_Literature.jpg`, `LicenseShortName = CC BY-SA 3.0`, `Artist` = original uploader, `Credit` = transfer note. (Requested 800, received 960 — Wikimedia serves from a **pregenerated** size list [tshor T360589 note in MediaWiki `API:Imageinfo`]; the script must accept `thumburl` as-is rather than computing `{size}px-` itself.)
  - Same chain for "Hồ Hoàn Kiếm" → `Q1151254` → `Ho Hoan Kiem (13574475044).jpg`, **CC BY 2.0**, Flickr origin credit returned by the API. And "Bảo tàng Dân tộc học Việt Nam" → `Q1048345` → `Dan toc hoc 1.jpg`, CC BY-SA 3.0.

---

## 3. Photo-source options compared (license + provenance + effort)

### 3.1 Wikimedia Commons (RECOMMENDED for tiers 0–2)

- **Access**: `https://commons.wikimedia.org/w/api.php` — no key, free, POST-blocking for browsers, public. Official docs: Commons:API / MediaWiki API (`https://commons.wikimedia.org/wiki/Commons:API/MediaWiki`), and API:Geosearch (`https://www.mediawiki.org/wiki/API:Geosearch`) for coordinate search (`generator=geosearch&ggsnamespace=6`); the MediaWiki API itself is the reference for `prop=imageinfo` + `iiprop=extmetadata` + `iiurlwidth` (`https://www.mediawiki.org/wiki/API:Imageinfo`).
- **Thumbnail pattern**: `iiurlwidth` returns `thumburl`; or canonical `upload.wikimedia.org/wikipedia/commons/thumb/<h1>/<h2>/<file>/<N>px-<file>` via MD5 of the file name ([Stack Overflow #33689980, svick](https://stackoverflow.com/questions/33689980/get-thumbnail-image-from-wikimedia-commons)). **Prefer `iiurlwidth`** — it is immune to hashing bugs and, per T360589, returns a served (possibly larger) pregenerated size.
- **Hotlinking**: officially *allowed* (`Special:FilePath`, e.g. `…/Special:Redirect/file/Sample.png&width=300`) but **"not generally recommended"** — files may be renamed/deleted/vandalized, "hot spiders" are against policy, and **attribution/license obligations apply exactly as if you re-hosted** ([Commons:Reusing content outside Wikimedia/technical](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/technical)). For an offline-demo MVP, hotlinking the thumbnail is acceptable; record the `File:` page URL and license so a future self-host/CDN cache is trivial.
- **License reality**: images are individually licensed; `imageinfo.extmetadata` exposes `LicenseShortName`, `Artist`, `Credit`, `UsageTerms` — verified CC BY 2.0 / CC BY-SA 3.0 on the 3 live tests. **CC BY/BY-SA demand visible attribution**; this is why the "attribution not rendered" finding (§1.3) must be fixed in Tier 0. Not every file is free (e.g. some `pd`/fair-use edge), so the import must *read* `LicenseShortName` and skip undeclared/derivative-only files, mirroring Commons' own "Do not use or index" caution ([Commons:API](https://commons.wikimedia.org/wiki/Commons:API)).
- **Cost**: none. **Risk**: name disambiguation (use Wikidata `Q*` bridging, exact `P18`, never fuzzy-pick), 429 under bursts (measured), deletion of hotlinked files.

### 3.2 OpenStreetMap wikimedia/wikipedia/wikidata tags

Documented link scheme (`image=*`, `wikimedia_commons=File:…/Category:…`, `wikipedia=lang:Title`, `wikidata=Q…`, `flickr=…`, `mapillary=…`) — [OSM Wiki: Photo linking](https://wiki.openstreetmap.org/wiki/Photo_linking) and [Key:wikimedia_commons](https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons). `wikimedia_commons=File:` is a *direct* image; `wikimedia_commons=Category:` is a pointer to a gallery (needs a category-member pick, see §4 path C). Note the Wiki's own observation that `wikidata=*` + `wikimedia_commons=*` are partly redundant because Wikidata itself links Commons ([Key:wikimedia_commons](https://wiki.openstreetmap.org/wiki/Key:wikimedia_commons)). In our Hanoi scan, only 22 features carry any `wikimedia_commons`, and 1 is a real file — so treat tags as a **bootstrap, not coverage**.

OSM data itself is ODbL 1.0; user-facing OSM attribution already exists in the app (`Slot.nguon_url` links to openstreetmap.org, plan header shows "Dữ liệu OpenStreetMap" map legend).

### 3.3 Unsplash (api-key path, attribution tightly enforced)

- License: free commercial use, **attribution "appreciated" but not required** for direct downloads ([unsplash.com/license](https://unsplash.com/license)) — BUT the API Terms add hard obligations: **attribution of both Unsplash and the photographer with a clickable profile link, hotlink to Unsplash-hosted URLs, and trigger the per-photo download endpoint** ([unsplash.com/api-terms](https://unsplash.com/api-terms); corroborated independently by [LicenseOrg](https://www.licenseorg.com/blog/unsplash-license-attribution-required) and [PicDefense](https://picdefense.io/resources/source-intel/unsplash)). Free tier ~50 req/h demo → 5,000 req/h post-review, no paid API tier (third-party summaries; verify in [Unsplash docs](https://unsplash.com/documentation)). **No indemnification on the free tier**.
- Fit for MVP: poor — needs a key, adds a persistent attribution banner + download-tracking integration, and its search relevance for specific Hanoi POIs is weaker than Commons' item-level linking. Best reserved for *generic* hero/placeholder imagery if ever needed.

### 3.4 Google Places Photo API (paid, live-fetch only)

- Access via Places API (New) `photometadatas`/`Place Photos`: requires a **Google Cloud API key + billing**; ~$7 / 1,000 photo requests (metered pricing cited in [Places billing](https://developers.google.com/maps/billing-and-pricing/pricing) and corroborated by [apio.sh](https://apio.sh/apis/google-places)); photo `name`s **expire and must not be cached**, and policy **prohibits pre-fetch/cache/store** — only `place_id` may be stored indefinitely; display requires Google attribution + author attribution where returned ([Places API Policies](https://developers.google.com/maps/documentation/places/web-service/policies), [Place Photos](https://developers.google.com/maps/documentation/places/web-service/place-photos)).
- Fit: violates the frozen "offline/provenance/determinism" constraint on multiple axes (paid, no caching, TOS display requirements, needs a Maps account). Reject for MVP; revisit as a live-fetch enrichment only if commercial.

### 3.5 Flickr (api-key; per-photo license)

- API default is **non-commercial**, commercial "by prior arrangement"; API key required (`flickr.photos.search` supports geo + `license=` filters) ([Flickr Services](https://www.flickr.com/services/api/), [flickr.photos.search](https://www.flickr.com/services/api/flickr.photos.search.html)). Per-photo license varies (many CC; some all-rights-reserved), so each photo needs license filtering + attribution ([Photo SE #6842](https://photo.stackexchange.com/questions/6842/how-to-attribute-flickr-creative-commons-photos-online)). Commercial activity on Flickr itself is Pro-only ([Flickr Commercial Use Policy](https://www.flickrhelp.com/hc/en-us/articles/4404057965332-Flickr-Commercial-Use-Policy)).
- Fit: another key + license gatekeeping with no obvious advantage over Commons for a Hanoi MVP; skip. (OSM `flickr=` tags measured at **0** in the bbox — the integration surface doesn't even exist here.)

### 3.6 Bottom line

Free **Commons (+ OSM/Wikidata as the index)** is the only stack that fits "real source, provenance, api-key-free, deterministic, non-commercial demo" — and it was proven end-to-end this session. Paid sources only matter for the café/restaurant majority that open data can't cover; defer to Tier 3.

---

## 4. Concrete MVP plan — `backend/scripts/enrich_images.py`

### 4.1 Input contract (no changes to the core catalogue)

Keep `data/places.json` as the immutable verified source of truth; write a **separate overlay** `backend/data/place_images.json` keyed by stable `osm-{type}-{id}` (or curated id). `image_for()` (`data.py:72-76`) becomes the merge point: `place.image_url` → overlay → static map. The overlay survives weekly re-imports (same keys) and separate re-runs are idempotent by key. In prod, the same script writes `dia_diem.hinh_anh` + `dia_diem.hinh_anh_meta` (JSON) instead. This preserves determinism: images never change the algorithm, routing, or scheduling — they are pure presentation.

### 4.2 Resolution cascade (api-key-free, all validated)

For each place, try in order, stop at first hit:

1. **`wikidata=Q…`** → `wbgetentities?ids=Q…&props=claims&claims=P18` → first P18 file → Commons `imageinfo&iiurlwidth=800&iiprop=url|extmetadata|mime|size` → store `{url, thumb_url, file_page, license, artist, credit, fetched_at, wikidata_id}`, skip if MIME not `image/jpeg|png|webp` or license undeclared. (Primary; covered **41/4,749** features.)
2. **`wikipedia=lang:Title`** → resolve title → wikidata via `wbgetentities?action=wbgetentities&sites=*&titles=…` (or `prop=pageimages` on the Wikipedia API as a lighter path) → continue as (1). (Primary bridge for the **40** wikipedia-tagged.)
3. **`wikimedia_commons=File:*`** → direct Commons file, same `imageinfo` call. (Only **1** in bbox today, but cheap.)
4. **`image=<https url>`** → validate `https` + content sniff; rare (**3**), treat as provisional, never hotlink non-https. (Sources: [Photo linking](https://wiki.openstreetmap.org/wiki/Photo_linking).)
5. **Curated must-have map** — extend the current 12 into ~30 headline files resolved once via the same pipeline (Lăng Bác, Hoàn Kiếm, Temple of Literature, Ho Chi Minh Mausoleum, Imperial Citadel, Bảo tàng Dân tộc học, Nhà hát Lớn, Trấn Quốc, Long Biên, etc.) and **delete the 7 dead keys** from `PLACE_IMAGE_URLS`. This is the Tier 0 deliverable and it is basically *maintenance of existing code*, not new infra.
6. **Kind-gated geosearch fallback** for `dia_danh|bao_tang|cong_vien` only (not cafés/restaurants/markets): `generator=geosearch&ggsnamespace=6&ggsradius=250&ggslimit=5&prop=imageinfo&iiurlwidth=800` ([Commons:API/MediaWiki](https://commons.wikimedia.org/wiki/Commons:API/MediaWiki), [API:Geosearch](https://www.mediawiki.org/wiki/API:Geosearch)); pick nearest file >= 640 px whose `LicenseShortName` is declared; still record full provenance. Tier 2.

No image anywhere → leave `null`; the app's existing `brokenImages` + `+no-photo` fallback path (PlanView without a broken <img>) degrades gracefully to a text-only slot. **Never** fall back to a random photo of the same *name* from a fuzzy match — that is how provenance gets invented, which violates the frozen "nguồn thật và provenance" intent.

### 4.3 Throttling & retries (empirically necessary)

- Measured **429** from `commons.wikimedia.org` on a 12-URL burst and **504** from Overpass twins today.
- Enforce ~1 req/s to Commons (sleep+jitter), exponential backoff on 429/5xx, cap per run (e.g. 300 resolutions), store partial results, resume by key. Run off-peak (e.g. Sunday 04:00) and *not* inside the request path.

### 4.4 Schema surface (minimal)

- Local JSON: no schema change; overlay file + `data.py` merge.
- PostgreSQL: reuse `hinh_anh text` (`0001_initial.sql:7`) for the cover URL and add `hinh_anh_meta jsonb` via the idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` pattern used throughout `0001_initial.sql:87-89,131-140` — no alembic stamp needed. `seed_postgres.py` keeps inserting `NULL`; the enrich script back-fills. `Place` data class is untouched (already has `image_url/image_credit`).

### 4.5 Effort & risk estimate (person-days, single dev)

| Step | Effort | Top risk | Mitigation |
|---|---|---|---|
| T0 curated map re-key + render `anh_nguon` | 0.5–1 d | attribution still partial in PDF/cal | render credit under photo + PDF credit block |
| T1 enrich script (cascade 1–4) + overlay + seed | 2–3 d | 429/504, P18 license variance | throttle/retry, skip undeclared licenses |
| T1 admin dashboard image metrics | 0.5 d | — | add `image_coverage_percent` next to `source_url_coverage` (`admin.py:168`) |
| T2 geosearch + kind placeholder | 1–2 d | wrong-nearest-file | kind gate + nearest/by-radius + min-width |
| T3 paid sources | defer | TOS/caching | only when food/drink coverage is a product blocker |

Total Tier 0–1 ≈ **3–5 person-days**, no new dependencies, no keys, no budget, deterministic output.

---

## 5. Data freshness for the catalogue itself

### 5.1 What "fresh" means here

The frozen spec says OSRM matrices are recomputed **offline weekly** (README: "OSRM ma trận … Ðã kiểm chứng"; `build_osrm_matrix.py`). The OSM catalogue lives a long tail — cafes open/close, hours change — and the importer already stamps `fetched_at` (`import_osm_places.py:124,134`). Recommendation:

- **Keep the current contract**: weekly batch re-import **outside the request path** (`import_osm_places.py` → `places.json` → `ensure_local_data.py` seeds only when empty, `ensure_local_data.py:15-20`). Add an `--overwrite`/`--force` flag so the demo keeps the guarantee "re-seed when data changed, never merge non-verified".
- **Admin-triggered refresh** (nice-to-have, Tier 2): `POST /api/admin/catalog/refresh` must shell out to the script and return `fetched_at` + diff counts, *not* re-run routing live; keep the request path offline to preserve determinism/`rate limiter fail-closed` behavior.
- **Weekly cadence tuned to Overpass**: single Hanoi bbox run is small; measured reliability was flaky (1 ok + 2×504), so wrap in mirror fallback + retry, and only promote a new `places.json` on: count stable (not -X%/-marginally), `fetched_at` advanced, coverage passes minimums (the `passes_minimum` logic already in `import_osm_places.py:141` feeds admin quality).

### 5.2 Freshness metadata to store (match existing patterns)

Follow the exact provenance shape used by `weather.py:103-108` and `inventory.py:104-111` (`provider`, `fetched_at`, `expires_at`):

- On each place (already mostly there): `source`, `source_url`, `fetched_at`.
- On each image: `provider: "Wikimedia Commons"`, `file_page` (the `File:` URL), `license` (`LicenseShortName`), `artist`, `credit`, `thumb_url`, `fetched_at`, optional `wikidata_id`.
- Surfaced in slơt as `anh_nguon` (exists) and should be rendered.

This gives the demo a claim it can defend: *every photo is a real Commons file, resolution-bridged through the OSM/Wikidata identifiers, with license+author+fetched-at recorded.*

---

## 6. Findings register (Blocker / High / Medium / Low / Note)

- **Blocker 1 — Production shows zero images.** `seed_postgres.py:57` writes `hinh_anh=NULL`; no code path ever enriches it. Even the 16 curated images are local-only (Loader `data.py:302-339` postgres path ignores `PLACE_IMAGE_URLS`). Fix: enrich + document local-vs-prod parity.
- **Blocker 2 — Attribution is never rendered.** `anh_nguon` is defined (`types.ts:1`) and emitted (`planner.py:1087`) but unused in the UI. Displaying CC BY/BY-SA photos without credit+license link is non-compliant. Fix: credit line under `slotPhoto` (`PlanView.tsx:223`) + hero (`PlanView.tsx:235`).
- **High 3 — The image store is 16 hardcoded URLs with 7 dead keys** and one file shared by nine places; no validation loop. Fix (Tier 0): curated ~30 via resolved Commons files + auto-check on every re-import.
- **High 4 — OSM import drops the exact tags needed for images** (`import_osm_places.py:70-116`). One-line fix unlocks 40–50 real images today; without it, enrichment has to re-query Overpass for the whole bbox on every run.
- **High 5 — No scheduled refresh exists.** Nothing re-runs the importer; the catalogue `fetched_at` is a one-time snapshot (`2026-08-06`). Weekly offline job + admin visibility required to keep the "data có nguồn thật và provenance" promise.
- **Medium — 429/504 rate surprises** measured this session; batch tooling must throttle & retry, and "weekly cron" must tolerate failed runs gracefully.
- **Medium — Name disambiguation** for places missing wikidata/wikipedia (most of the catalogue). Mitigation: only resolve through `Q*` graphs and exact `P18`/`File:`; never fuzzy-match on name.
- **Low — Geosearch fallback breadth** limited to sights; per-item err rate higher; keep as Tier 2.
- **Note — Paid sources (Google Places Photo $7/1K, Unsplash attribution+download-tracking, Flickr commercial-by-arrangement) violate the offline/provenance/TOS constraints**; they are Tier 3 options for food/drink photo coverage only if the product requires it.

---

## 7. Recommended sequencing

- **Tier 0 (now, ≤1 d):** re-key curated map to ~30 verified Commons files; delete dead keys; render `anh_nguon` under photos; expose `image_coverage_percent` in admin quality.
- **Tier 1 (next sprint, ≤3 d):** `enrich_images.py` cascade (wikidata→P18→Commons; wikipedia→…; File:; image url) + `place_images.json` overlay + Postgres `hinh_anh`/`hinh_anh_meta` backfill + weekly offline job + admin refresh endpoint (shelled).
- **Tier 2 (optional):** kind-gated geosearch fallback; thematic placeholders for food/cafes so a non-photo slot never looks broken.
- **Tier 3 (deferred):** paid/commercial sources, self-hosted image cache, and 3rd-party POI feeds with image fields — only when demonstrated by real usage data.

---

## Executive summary (250 words)

The Hanoi MVP has a place-data plumbing problem, not an algorithm problem. Today, 3,529 verified OSM+curated places exist, yet **only 16 (0.45%) ever display an image — and that figure is 0 in the PostgreSQL production path**, because seeding writes `hinh_anh=NULL` and the curated Commons URLs live only in local `data.py`. The existing import respects provenance (ODbL, `fetched_at`, source_url) but **throws away the exact OSM tags that unlock photos** — wikipedia/wikidata/wikimedia_commons/image — leaving no cross-reference to build from. A live scan of the same bbox shows the real open-data coverage: ~40 `wikipedia`, 41 `wikidata`, 22 `wikimedia_commons` tags, focused on museums/attractions/parks. I validated end-to-end, live, the api-key-free pipeline that fixes this: OSM wikidata → Wikidata `P18` → Commons file → `imageinfo&iiurlwidth=800` returns thumbnail URL, **license, artist and credit** (CC BY 2.0 / CC BY-SA 3.0 observed). Two blockers gate the fix: **attribution is never rendered** (the slot's `anh_nguon` exists but the UI ignores it), and the 23 hardcoded `Special:FilePath` URLs contain 7 dead keys with one file shared across nine places. Recommending: Tier 0 re-key ~30 curated places + render credits (~1 day); Tier 1 a throttled, deterministic `enrich_images.py` overlay + `hinh_anh`/`hinh_anh_meta` + weekly offline refresh + admin image metrics (~3 days, no keys, no budget); Tier 2 gated Commons geosearch; Tier 3 paid sources (Google Places $7/1K, Unsplash attribution+download policy, Flickr commercial-arrangement) only for food/drink coverage that open data cannot provide.

---

## Top 5 most concerning findings

1. **Production images = 0.** `seed_postgres.py:57` inserts `hinh_anh=NULL`; the postgres load path (`data.py:331`) then maps NULL → no image. The feature silently doesn't exist in any non-local deployment.
2. **All CC-BY photos are currently displayed without attribution** — `anh_nguon` is carried on the slot (`planner.py:1087`, `types.ts:1`) but never rendered; a legal/compliance violation, not a styling gap.
3. **OSM import discards the resolving tags** (`import_osm_places.py:70-116`): `wikipedia`, `wikidata`, `wikimedia_commons`, `image` are all in the Overpass payload and dropped, so the cheap enrichment path is closed until a 1-line-ish change.
4. **The photo store is 12 unique hardcoded files** (7 dead keys, `Hanoi_shophouse_2.jpg` reused for nine places) with zero validation; `brokenImages` masks failures instead of fixing them.
5. **No freshness machinery at all** — the catalogue is a one-time snapshot (`fetched_at 2026-08-06`) with no weekly job, and live Overpass returned 504 twice today: a naive cron will silently produce stale data.

---

## Confidence

**7 / 10.**

*Ground-truth tally:* repository code — read directly (data.py, import/seed/ensure scripts, planner.py, PlanView.tsx, types.ts, config/admin/weather/inventory, schema SQL): **11 externally-verifiable facts**, all confirmed against the working tree. Live external checks this session — Overpass tag census (4,749 features), Commons `Special:FilePath`, Commons geosearch, Wikidata→Commons resolution incl. license/artist for 3 subjects, 429-under-burst, 504 on Overpass mirrors: **7 external facts**. That's a solid empirical base; however (a) Overpass counts are a point-in-time that degrades daily as mappers tag more, (b) I could not fully audit `pdf_export.py`/`plans.py` render paths for image credit (out of lane overlap), (c) Commons file deletion/rename risk is probabilistic, not measured, and (d) pricing/rate-limit figures for Unsplash/Flickr/Google come partly from third-party summary pages rather than primary docs (flagged inline). Model judgment, not externally verified: effort estimates, tier ordering, and the "food photos must wait for paid" claim. Do not round up: **7/10**.

<div hidden>lanes: agents 1 (UI), 2 (itinerary), 3 (this), 4 (links), 5 (manual change), 6 (duration)</div>