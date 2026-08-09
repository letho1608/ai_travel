# Deep-Dive Lane 01 — Core Itinerary Generation Pipeline

**App:** "Mình Đi Đâu Thế" (Hanoi-only AI itinerary generator)
**Repo:** `D:\Code\aithucchien\ai_travel`
**Lane:** Core itinerary generation pipeline (`backend/app/pipeline/planner.py`, `routing.py`, `services/ai.py`, `data.py`, `services/osm_verify.py`, `services/weather.py`)
**Other lanes (not duplicated here):** frontend UI/UX & chatbot-input; replan/refine/swipe/versions; share button & platform integration.
**Method:** Read every file in the pipeline end-to-end, then ran 5 custom probe scripts on Python 3.10.8 (mock AI mode, `APP_ENV=local`, `AI_MODE=mock`, with the `datetime.UTC` shim), plus the project's own `test_pipeline.py` suite. Research only — no source files modified.

---

## 0. Honest verdict up front

**The core pipeline does not work as advertised.** In the default `AI_MODE=mock` mode there is effectively no "AI" at all: every itinerary is `candidates[:count]` from a list that is (a) sorted mostly by *distance from a hardcoded Hoàn Kiếm origin* when no intent matches, and (b) then **rotated by a seed hash that pushes the single best intent match out of the selection window**. A "chợ đêm" (night market) request produces seven random coffee shops scheduled 08:00–15:41. The night market *never* appears for a pure night query because the Vietnamese letter "đ" (U+0111) is silently deleted by `_ascii_fold` — "chợ đêm" becomes "cho em" and no night-intent term ever matches. When the "evening" machinery does fire, nightlife-tagged places whose `open_hour` defaults to 7 are scheduled at 08:00–10:00 in the morning. In LLM mode (groq/deepseek) the "AI" is allowed to *name* places but is wrapped in a deterministic cage that pins them to catalog hours (all hardcoded 7–22, cost 0), and the fuzzy catalog matcher maps the query "Phố cổ Hà Nội" to a **phở noodle restaurant** and any night-market name to an OSM copy with `open_hour=7`.

The three user complaints are all **confirmed and reproduced**:
- (a) *Generated itineraries are worse than a plain LLM* — confirmed; in mock mode they are near-random coffee-shop runs regardless of intent.
- (b) *Night market scheduled in the morning or never appears* — confirmed, both failure modes reproduced.
- (c) *Hồ Gươm / Hồ Tây / Lăng Bác hardcoded into every Hanoi plan* — confirmed; all four anchors are forced by `_highlight_places` for any context containing "Hà Nội"/"du lịch"/etc., and the project's own test suite **asserts this as intended behavior**.

---

## 1. Evidence table — starting claims vs. my independent runs

All probes ran `python` 3.10.8 with `AI_MODE=mock`, `APP_ENV=local`, `sys.path` → `backend`, and `datetime.UTC = datetime.timezone.utc` before importing. Full `build_plan` output (place ids, times) was printed; key rows below.

| # | Starting claim (from brief) | My run | Verdict |
|---|---|---|---|
| 1 | `_ascii_fold` drops "đ": "chợ đêm" → "cho em", night intent never matches | `_ascii_fold("chợ đêm")` = `'cho em'`; `relevant_tags("chợ đêm")` = `{cho, cho_em, em}`; `_intent_profiles` → `[]`. "ban đêm" → `{ban, ban_em, em}` → `[]`; "đêm" → `{em}` → `[]` | **CONFIRMED** |
| 2 | "đi chơi buổi tối" yields 7 coffee shops | `build_plan` → Sinh Cafe, Snow Island, V cafe, Aventus, Trà Sữa BoBaBop, She Coffe, quán trà sữa, all 08:00–16:04. Night profile **is** matched (`toi`/`buoi_toi` survive folding) — so this case is NOT the fold bug | **CONFIRMED**, but root cause = rotation (row 4), not folding |
| 3 | "chợ đêm" → 7 coffee shops, no night market | `build_plan` → She Coffe, Trung tâm Tinh hoa làng nghề, quán trà sữa, cafe tưởng tượng, The Youth AOF, Coffe Number 1, teafox, 08:00–15:41. No night market, no ≥17:00 slot | **CONFIRMED** |
| 4 | Seed rotation `intent_offset = seed % len(intent_matches)` pushes highest-intent place out of window | `curated-cho-dem-dong-xuan` has `_intent_score` = **8** (the global max for "đi chơi buổi tối"), pre-rotation index **0** in `intent_matches`; `offset = seed % 51 = 32`; post-rotation index **19**; `count=7` → **PUSHED OUT** | **CONFIRMED**, proven arithmetically |
| 5 | `_highlight_places` + `HANOI_HIGHLIGHT_IDS` hardcode anchors | `_highlight_places` returns `[ho-guom, lang-bac, ho-tay, pho-co]` for any context containing `ha_noi/du_lich/...` OR `ho_guom/ho_tay/lang_bac/ba_dinh/pho_co`. Reproduced for "cà phê và ẩm thực Hà Nội", "Hồ Gươm", "Hồ Tây", "Lăng Bác", "xem bảo tàng Hà Nội", "Một ngày văn hóa Hà Nội" (the frontend *culture chip*) | **CONFIRMED** |
| 6 | Night market lands in the morning via OSM-verified default hours (open 7 close 22) | `osm_verify.py:174-175` sets `open_hour=7, close_hour=22`. Simulated a `Nominatim` "Chợ đêm Đồng Xuân" through `_ordered_route` + the slot scheduler → classified `daytime`, scheduled **08:00–09:00** (probe 11). Also catalog copy `osm-node-4489385889` "Chợ Đêm Hàng Đào – Đồng Xuân" is `open 7 / close 22` and is what `_catalog_match` resolves any night-market name to | **CONFIRMED** (two independent paths) |
| 7 | Multi-day split after sorting → does it group evening to day 2? | Yes, but with a caveat: for "đi chơi Hà Nội 2 ngày", day 2 = Hồ Tây 08:00, Hàng Đào **09:32 AM**, then a **7-hour dead zone** 10:07→17:00 (Tạ Hiện waits for 17:00 via `cursor = max(cursor, opening)`). Evening places land on day 2 only because the tail of the route is the evening segment | **PARTIALLY CONFIRMED** |
| 8 | Deterministic seed → same input gives same output | Same request twice → identical place sequence (probe 7). Different `nonce` or `ma_phien` → different sequence | **CONFIRMED** |
| 9 | 3508-place catalog is the pool | **REFUTED in practice**: `is_routable` (`routing.py:62-67`) limits the pool to the 50 OSM ids present in `distance_matrix.json` + curated/Nominatim. Only **50 of 3508** catalog places are ever eligible. And all 3508 have `open_hour=7, close_hour=22, cost=0, duration_min=60`; **zero** catalog places are evening/nightlife | **REFUTED** (catalog is effectively 68 usable places) |

Additional findings my runs surfaced that the brief did not predict:
- **"Phố cổ Hà Nội" resolves to "Phở hà nội" (a phở restaurant)** via `_catalog_match` token fuzziness (probe 10) — a direct "LLM says iconic place, user gets a noodle shop" failure.
- The frontend's own duration inference rejects the string "chợ đêm" (it keeps "đ", so the `/dem/` regex never matches) — a UX blocker before the backend is even reached.
- The project's 16 `test_pipeline.py` tests all pass, and two of them *encode* the anchor-forcing and the fragile night behavior as desired outcomes.

---

## 2. Blocker — `_ascii_fold` deletes Vietnamese "đ", making core intent terms unreachable

**Code:** `planner.py:131-137`, used by `relevant_tags` (`planner.py:140-149`).

```python
def _ascii_fold(value: str) -> str:
    return (unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
            .decode("ascii").lower())
```

`unicodedata.normalize("NFKD", "đ")` returns `"đ"` unchanged — U+0111 LATIN SMALL LETTER D WITH STROKE has **no canonical or compatibility decomposition** (the stroke is not a combining mark). The `"ascii", "ignore"` encoder therefore deletes it silently. My probe 2 confirmed: `đ → ''`, while `ơ→o`, `ư→u`, `ữ→u`, `â→a`, `ê→e`, `ô→o`, `ă→a` all decompose fine. So the only truly destructive case in Vietnamese is exactly the "đ" that begins the country's most common night-market word.

Measured folding + intent-match outcomes (probe 1):

| Input | `_ascii_fold` | INTENT profile reached? |
|---|---|---|
| `chợ đêm` | `cho em` | none |
| `đêm` | `em` | none |
| `ban đêm` | `ban em` | none |
| `chợ đêm Hàng Đào` | `cho em hang ao` | none |
| `đồng xuân` / `Đồng Xuân` | `ong xuan` | none (also no `dong` term anywhere) |
| `Hàng Đào` | `hang ao` | none (`OLD_QUARTER_TERMS` has `hang_dao`) |
| `đi bộ` | `i bo` | none (walk profile term is `di_bo`) |
| `Hồ Gươm` / `Lăng Bác` / `Hồ Tây` | `ho guom` / `lang bac` / `ho tay` | none via terms, but **reached via the separate tag check** `planner.py:195` |
| `đi chơi buổi tối` | `i choi buoi toi` | night (`toi`, `buoi_toi`) |
| `tối nay` | `toi nay` | night (`toi`) |
| `phố cổ` | `pho co` | hanoi_highlights (`pho_co`) |

Consequences:
1. `_wants_night` (`planner.py:214-215`) is False for "chợ đêm"/"ban đêm"/"đêm", so `HANOI_NIGHT_IDS` are never added to highlights (`planner.py:202`) and the `open_hour>=17` exclusion filter for short trips (`planner.py:249-253`) is inverted (it *removes* evening places when night intent is absent — correct direction, but the intent is wrongly absent).
2. `_wants_old_quarter` (`planner.py:222-228`) is False for "chợ đêm", so **every curated place tagged `pho_co` — including `curated-cho-dem-dong-xuan` itself — is excluded from candidates** by the filter at `planner.py:244-248`. The night market is not just ranked low; for a pure night-market query it is *deleted from the candidate universe entirely*.
3. "đi bộ" → `i bo` never triggers the `walk` profile, so a major requested activity type is dead.
4. `hang_dao` in `OLD_QUARTER_TERMS` is unreachable; `hang_duong`, `hang_ma`, `hang_ngang`, `hang_khay` are also unreachable via their street names because of the same deletion ("Hàng Mã"→"hang ma" does match `hang_ma` — but "Hàng Đào" and "Hàng Đường" do not).

Severity: **Blocker** (destroys the app's central promise for the single most iconic Vietnamese night activity). Note the frontend `normalizeText` (`Planner.tsx:62-64`) uses NFD + strip combining marks, which *keeps* "đ" — so the frontend and backend disagree on how "chợ đêm" folds, which is why the frontend duration inference (`Planner.tsx:71`, regex `/dem/`) rejects "chợ đêm" while the backend silently mangles it.

---

## 3. Blocker — the "3508-place catalog" is effectively 68 places, and none of it is nocturnal

**Code:** `routing.py:62-67` (`is_routable`), `data.py:45-65` (loader), `import_osm_places.py:91-111`, `distance_matrix.json`.

`is_routable(place)` returns True only if the place is in `ROUTABLE_PLACE_IDS` (the 50 ids in `distance_matrix.json`) or has `source in {"curated", "Nominatim"}`. My run showed the matrix's 50 ids are exactly the 50 catalog entries that intersect it; the other 3458 catalog entries have source `"OpenStreetMap"` and are never routable. The **effective candidate universe is 50 OSM places (14 museums + 36 cafés) + 18 curated anchors = 68**. There are no routable restaurants, markets, parks, or landmarks from the catalog — the 155 catalog markets, 1489 restaurants and 250 parks are all dead weight in local mode.

Data-quality audit of the 3508 (probe on `places.json`):
- `open_hour` distribution: **7 for all 3508**; `close_hour`: **22 for all 3508**. `import_osm_places.py:102-103` hardcodes these even though line 104 captures `opening_hours_raw` from OSM and then **throws it away**.
- `cost`: **0 for all**; `duration_min`: **60 for all** (`import_osm_places.py:99-100`).
- Tags: only 1829/3508 have any tags, and they are OSM raw values (`cuisine`, `outdoor_seating`, `wheelchair`, `tourism`, `leisure`, `historic` — `import_osm_places.py:83-90`). **Zero** catalog places carry `nightlife`, `cho_dem`, `night_market`, `ho_guom`, `pho_co`, `am_thuc`, or any of the semantic tags the intent system scores on. The `cho` (market) kind has almost no tags (only 3 places tagged `attraction`).

Consequences:
- The entire evening machinery (`_ordered_route` evening classification, `cursor = max(cursor, opening)` waits, the `open_hour>=17` filters) has **no data to act on**: the only evening-classified places in the whole system are the curated anchors `cho-dem-dong-xuan` (open 18), `pho-ta-hien` (open 17), and the nightlife-tagged `hang-buom`/`hang-dao`/`pho-co-ha-noi` (open 7 — see finding 5).
- The intent-scoring system (`_intent_score`, `planner.py:179-188`) can never score a catalog place highly for `night`, because no catalog place has night tags; the top of the `night` ranking is always the curated market and old-quarter streets (confirmed in probe 4's top-5).
- "An optimized itinerary within budget" is fictional: every place costs 0 VND, so `_select_within_budget` (`planner.py:312-321`) selects the first `count` regardless of budget; `chi_phi_moi_nguoi` is always 0 (probe 9: budget of 50,000 VND and 1,000,000 VND both returned 7 places at 0 cost). The frontend hardcodes `ngan_sach: 1000000` (`Planner.tsx:116`) and the refine feature multiplies budgets by 0.8 (`plans.py:442-443`) — all of it meaningless against a 0-cost catalog.

Severity: **Blocker** (the catalog cannot express night markets, real hours, or real prices; the pool is 1.9% of what the UI implies).

---

## 4. High — seed rotation pushes the best intent match out of the selection window

**Code:** `choose_candidates` `planner.py:272-280`; consumed by `_select_ai_places` (`planner.py:345-364`) where the mock adapter returns `candidates[:count]` (`ai.py:84`).

For "đi chơi buổi tối" (night profile active, 65 candidates, 51 intent matches), my exact replication of the sort (probe 4):

```
curated-cho-dem-dong-xuan   _intent_score = 8   pre-rotation index 0  (best match)
intent_offset = seed % 51   = 32
post-rotation index         = 19                count (ca_ngay) = 7
=> night market is PUSHED OUT; candidates[:7] = 7 cafés, all score 3.
```

The rotation exists to make same-context requests produce different plans (the test at `test_pipeline.py:43-52` asserts nonce-varied non-identical outputs), but it rotates the *entire* intent-sorted list by `seed % len(intent_matches)`, so the highest-intent place lands at index `len - offset` — virtually always outside the `[:count]` window whenever there are more intent matches than slots. The effect is anti-intent: **the most relevant place is the least likely to be selected**, and the itinerary is filled with mid-tier matches (cafés scoring 3) instead.

Note that because `_request_seed` (`planner.py:152-163`) hashes context + duration + people + budget + `ma_phien` + `nonce`, whether the night market appears for an evening query is effectively a **lottery ticket per session**: for "đi chơi buổi tối 2 ngày" with a different `ma_phien` the market *did* land at index 6 of candidates and was scheduled at 19:55 (probe 5). Same user intent, different session → completely different relevance. This also makes the project's own night test (`test_pipeline.py:96-109`) pass only because its specific `ma_phien="test-session"` + `nonce` seed happens to rotate the market/Tạ Hiện into view — the test asserts the *union* of two possible stops and does not require the market itself.

Severity: **High** (deterministic anti-relevance; makes the planner non-reproducible in a harmful direction).

---

## 5. High — Hồ Gươm / Hồ Tây / Lăng Bác / Phố cổ forced into plans regardless of intent

**Code:** `_highlight_places` `planner.py:191-211`, `HANOI_HIGHLIGHT_IDS` `planner.py:94-99`, prompt bias `ai.py:133` and `ai.py:209-210`.

`wants_hanoi_highlights` is true if the context mentions any of `ha_noi/hanoi/du_lich/tham_quan/noi_tieng/lan_dau/classic/pho_co` **or** any of `ho_guom/ho_tay/lang_bac/ho_chi_minh/ba_dinh/pho_co`. When true, `_highlight_places` prepends **all four** `HANOI_HIGHLIGHT_IDS` (plus the two night ids if night terms match). Highlights are prepended *after* ranking and are exempt from the rotation (line 281: `highlights + [place for place in ordered if ...]`), so they always occupy the first slots.

Reproduced across contexts (probe 2/5/extra):

| Context | Anchors forced (first N slots) |
|---|---|
| `cà phê và ẩm thực Hà Nội` | Hồ Gươm, Lăng Bác, Hồ Tây, Phố cổ + 3 cafés — a coffee/food request |
| `xem bảo tàng Hà Nội` | Lăng Bác 08:00 + museums + Hồ Gươm, Hồ Tây, Phố cổ |
| `Một ngày văn hóa Hà Nội` (culture chip) | all 4, before any museum |
| `Hồ Gươm` | all 4 — and Lăng Bác is scheduled **first** at 08:00 because its `close_hour=17` sorts it to the head of the daytime route |
| `đi bộ hồ Gươm` | all 4 |
| `du lịch Hà Nội` | all 4 + night market at 18:00 + Phố cổ |

So asking for "Hồ Gươm" returns Hồ Gươm **plus** Lăng Bác, Hồ Tây, Phố cổ; asking for "cà phê và ẩm thực" returns four sightseeing anchors before the requested coffee/food. This is the direct cause of complaint (c). It is *tested-as-intended*: `test_pipeline.py:81-93` asserts all four appear for a "du lịch Hà Nội lần đầu" query, and the ai.py prompt (`ai.py:133` "Prefer iconic Hanoi anchors when relevant"; `ai.py:209-210` "include iconic places such as Hồ Gươm, Lăng..., Hồ Tây, and Phố cổ") biases the LLM the same way.

Severity: **High** (systematically overrides user intent; the app's own defaults and tests bake it in).

---

## 6. High — "evening" places are scheduled in the morning whenever their `open_hour` is not actually late

**Code:** `_ordered_route` `planner.py:471-490`, slot scheduler `planner.py:528-560`, `osm_verify.py:174-175`, curated data `data.py:159-168`.

`_ordered_route` classifies a place as evening if `open_hour >= 17` **or** `"nightlife" in tags` **or** `"cho_dem" in tags` (line 472). But the *scheduler* only honors `open_hour`:

```python
opening = cursor.replace(hour=place.open_hour, minute=0)
cursor = max(cursor, opening)          # planner.py:536-537
```

A place with `nightlife` tag but `open_hour=7` is routed into the evening segment yet **scheduled at whatever time the cursor has reached** — often morning/noon. Reproduced:
- `curated-hang-dao` (tags include `cho_dem, nightlife`; `open_hour=7`) → scheduled **09:32–10:07 AM** in "đi chơi Hà Nội 2 ngày" (probe 5).
- `curated-pho-co-ha-noi` (nightlife tag, open 7) → scheduled **15:27–16:57** in "cà phê và ẩm thực Hà Nội" when it is the only evening-classified place (no later opener pushes the cursor).
- In "du lịch Hà Nội" it lands at 19:20 only *because* `cho-dem-dong-xuan` (open 18) precedes it and drags the cursor to 18:00.

And for the "night market in the morning" complaint specifically, two independent paths (probe 10/11):
1. **Catalog copy:** `_catalog_match` resolves "Chợ đêm Đồng Xuân"/"Chợ đêm Hàng Đào" to `osm-node-4489385889` ("Chợ Đêm Hàng Đào – Đồng Xuân", kind `cho`, `open_hour=7`, `close_hour=22`, no night tags) — an OSM snapshot of the very market whose curated twin has `open_hour=18`. Classified `daytime`, scheduled ~08:00.
2. **Nominatim verify:** any LLM-named night market not in the catalog becomes a `Place` with `open_hour=7, close_hour=22` and tags `("osm_verified","llm_suggested")` (`osm_verify.py:164-178`) → same morning scheduling. My scheduler simulation put a `Nominatim` "Chợ đêm Đồng Xuân" at 10:13 AM after two daytime stops (probe 11).

The `visit_minutes` cap (`planner.py:538`, `min(duration_min, 40)` for `vai_gio`) and the `end > closing` raise (`planner.py:541`) are otherwise consistent — but the *evening* concept is expressed in tags while the *scheduler* only reads `open_hour`, and the two data sources disagree for 4 of the 6 curated evening-tagged places.

Severity: **High** (complaint (b)'s morning-scheduling mode; also produces afternoon slots for nightlife venues).

---

## 7. High — fuzzy catalog match maps "Phố cổ Hà Nội" to a phở restaurant; LLM-named places get wrong hours

**Code:** `_catalog_match` `osm_verify.py:100-119`, `_select_llm_first_places` `planner.py:367-405`, draft prompt `ai.py:205-231`.

`_catalog_match` accepts a place if the folded needles share `>= max(2, min(len(needle_tokens), 3))` tokens with the catalog place's folded name, choosing the nearest by distance. Because "phố" (street) and "phở" (noodle) both fold to `pho`, my probe 10 found:

- **"Phố cổ Hà Nội"** → matches `osm-node-10298717234` **"Phở hà nội"** (a `nha_hang`, 21.0253,105.8517) — nearer to the Hoàn Kiếm origin than the curated "Phố cổ Hà Nội" (21.0341,105.8523), so the tie-break picks the noodle shop. An LLM that correctly names the iconic district produces a phở restaurant stop.
- **"Chợ đêm Đồng Xuân" / "Chợ đêm Hàng Đào"** → the OSM copy with `open_hour=7` (finding 6 path 1).
- **"Đồng Xuân market", "Hoàn Kiếm walking street", "Nhà thờ Lớn Hà Nội", "Một cột pagoda"** → no match → Nominatim (7–22 default).

How much of a real-mode itinerary is actually "LLM-driven"? `_select_llm_first_places` calls `draft_itinerary_places(context, count, lang)` (no candidate list is sent — `ai.py:205-231`), so the LLM proposes *names*; each is then resolved to a catalog/Nominatim `Place`, and **the final schedule, ordering, times, costs, descriptions, and day-split are 100% deterministic** (`_ordered_route` + scheduler + `_select_within_budget` fallback). The LLM's free-form answer is funneled through a cage that (a) accepts at most 2 shared tokens of name similarity, (b) assigns hours it never saw, and (c) throws away the LLM's pacing. Also: `_select_llm_first_places` does **not** apply `is_routable`, so LLM-resolved catalog places that are *not* in the matrix (e.g., `osm-node-4489385889`) can enter the plan even though the deterministic path would reject them. If the LLM names fewer than `count` resolvable places, the remainder are filled from the deterministic candidate list (lines 395-402). And in mock mode `draft_itinerary_places` returns `[]` (`ai.py:92`), so the LLM-first path is inert by default.

Net assessment: the LLM can make the itinerary *worse* than the cage (name→wrong-place resolution, no routability check) and the cage cannot make it *good* (68-place pool, no hours/prices data). The claim "worse than a plain LLM" is therefore structurally expected, not an accident of prompting.

Severity: **High** (in LLM mode, iconic names can silently become wrong places; the mock mode is where the product actually runs by default).

---

## 8. Medium — multi-day split groups evening onto day 2 but leaves multi-hour dead zones

**Code:** `build_plan` `planner.py:524-525` (`split_index = (len(route)+1)//2`), route order `planner.py:471-490`.

The route is built as `daytime… + evening…` and then cut after the sort, so the evening tail does land on day 2 — that part works. But because the split happens **after** `_ordered_route`, day 1 absorbs all morning-capable places and day 2 is left with afternoon gaps that only an evening opener can fill. Reproduced for "đi chơi Hà Nội 2 ngày" (probe 5):

```
Ngày 1: Lăng Bác 08:00, Hàng Dầu, Hàng Gai, Hàng Bạc, Hồ Gươm 11:03
Ngày 2: Hồ Tây 08:00, Hàng Đào 09:32, [gap 10:07 → 17:00], Tạ Hiện 17:00, Hàng Buồm 18:20, Phố cổ 19:00
```

The 10:07→17:00 hole is produced by `cursor = max(cursor, opening)` waiting for Tạ Hiện's 17:00 open. For "chợ đêm 2 ngày" there is no night market at all (fold bug, finding 2) and day 2 is five more random museums/cafés at 08:00–13:10 (probe 5). The split should interleave day-2 daytime places into the gap before committing the evening segment, but the current order commits everything first.

Severity: **Medium** (functional 2-day plans, but with obvious unfillable dead time).

---

## 9. Medium — `validate_plan` skips opening-hours enforcement for LLM-verified places

**Code:** `validate_plan` `planner.py:287-309`.

`by_id = {place.id: place for place in PLACES}` (line 294) — places created at runtime by `verify_place_name` (ids `osm-verified-…`) are **not in `PLACES`**, so `place = by_id.get(...)` returns `None` and the opening-hours check (lines 301-305) is silently skipped for every LLM-verified slot. The check itself is sound for catalog places: `f"{open_hour:02d}:00" <= slot["bat_dau"]` lexicographic comparison of zero-padded `HH:MM` strings is correct, the `previous_end`/`ket_thuc` ordering check (line 299) is correct, and no off-by-one exists there. But "validated" plans containing OSM-verified places have no hour guarantees at all — the same class of place finding 6 shows being scheduled at 08:00.

The scheduler's own `end > closing` raise (`planner.py:541`) does guard generated slots for *catalog* places, but `swipe` (replan lane, `plans.py:374`) re-validates after swaps and would also miss hour violations for LLM-verified ids.

Severity: **Medium**.

---

## 10. Low/Note — `Asia/Bangkok` timezone labeling is wrong but currently harmless

**Code:** `plans.py:191` (`TZID=Asia/Bangkok` in `.ics`), `weather.py:118` (`timezone=Asia/Bangkok` for Open-Meteo).

Hanoi's IANA zone is `Asia/Ho_Chi_Minh`; `Asia/Bangkok` is Thailand's. Both are fixed UTC+7 with no DST (Vietnam abolished DST in 1975; Thailand has none), so every DTSTART/DTEND in the exported `.ics` and every forecast day is numerically identical to the correct value. This is a latent correctness/accuracy bug (wrong zone name on the wire, which some calendar clients display as "Bangkok") but produces no wrong times today. Same for the `datetime.combine(trip_date…, …)` wall-clock arithmetic in the scheduler (`planner.py:529`) — all local, consistent.

Severity: **Low** (Note: the label is wrong; the math is fine).

---

## 11. Medium/Note — budget, determinism, and "verification" are cosmetic

- **Budget is a no-op** (finding 3): all 3508 + curated anchors are `cost=0`, so `_select_within_budget` and `chi_phi_moi_nguoi` are decorative; `test_plan_never_exceeds_per_person_budget` (`test_pipeline.py:37-40`) passes trivially. The UI still shows an "estimated costs" figure of 0 and the refine flow rescales budgets (`plans.py:433-443`).
- **Determinism**: same context+duration+people+session+nonce → identical plan (probe 7); the nonce cache in the frontend (`Planner.tsx:40-60`) intentionally replays the same plan on identical resubmits. Different session → different plan via the seed rotation. So "same input gives same output" is true only within one session, and the *variation* it does provide is the harmful rotation of finding 4.
- **Tests bless the defects**: all 16 `test_pipeline.py` tests pass, but they assert (a) all four anchors for tourism queries (line 81-93), (b) a fragile OR-of-two-night-stops outcome that depends on the seed (line 96-109), and (c) nonce-varied non-identical outputs (line 43-52) — i.e., the rotation. The suite never exercises "chợ đêm" alone, never asserts *which* places, and cannot run on the stated Python 3.10 without a `datetime.UTC` shim (the codebase imports `from datetime import UTC`, which is 3.11+).

Severity: **Medium** (budget/UI lies) + **Note** (tests encode the bugs).

---

## 12. Severity summary

| # | Finding | Severity |
|---|---|---|
| 2 | `_ascii_fold` deletes "đ"; night/intent terms unreachable; curated night places excluded for pure night queries | **Blocker** |
| 3 | Catalog is 68 usable places (not 3508); zero evening places, zero prices, all hours 7–22 | **Blocker** |
| 4 | Seed rotation pushes the #1 intent match out of the selection window | **High** |
| 5 | Four iconic anchors forced into every "Hà Niji"/tourism/culture plan | **High** |
| 6 | Nightlife/cho_dem-tagged places with open_hour=7 scheduled in the morning; night market morning path | **High** |
| 7 | Fuzzy catalog match maps "Phố cổ Hà Nội"→"Phở hà nội"; LLM names get default hours; no routability check | **High** |
| 8 | Multi-day split leaves multi-hour dead zones on day 2 | **Medium** |
| 9 | `validate_plan` skips hours for LLM-verified places | **Medium** |
| 10 | TZID `Asia/Bangkok` wrong label, harmless today | **Low** |
| 11 | Budget no-op; tests bless the bugs | **Medium / Note** |

---

## 13. Executive summary (≈250 words)

The itinerary generator does not work as a useful, intent-faithful product in the mode it actually runs (mock) and is structurally incapable of being better than a plain LLM. I reproduced every reported failure. The night market is unreachable for a pure "chợ đêm" request for three stacked reasons: the `_ascii_fold` normalization silently deletes Vietnamese "đ" so the night intent never fires; that failure turns off the old-quarter allowance, so the curated night market and all old-quarter streets are filtered out of the candidate pool entirely; and where night intent *does* fire, a seed-based rotation moves the single highest-scoring night place (score 8, pre-rotation rank 1) to post-rotation rank 19 — outside the 7-slot window — so the itinerary fills with cafés. When evening places do appear, the scheduler only respects `open_hour` (7 for the OSM copy of Đồng Xuân market and for Nominatim-verified night markets), so "Chợ đêm" is scheduled at 08:00. The catalog itself is 68 usable places (50 routable OSM cafés/museums + 18 curated), all costing 0 VND with hours 7–22, so budgets, evening logic, and "verified place" claims are mostly decorative. Four iconic anchors are force-prepended to any context mentioning Hà Nội/tourism — including a coffee-and-food request — and the fuzzy name matcher turns "Phố cổ Hà Nội" into "Phở hà nội" noodle shop. All 16 pipeline tests pass because they encode the hardcoding as desired behavior and never test the failing phrases.

## 14. Top 5 most concerning findings

1. **"Chợ đêm" produces seven random coffee shops (08:00–15:41) with zero night content** — the fold bug + pho_co-exclusion + rotation stack to make the app's flagship example intent return nonsense (probe 5).
2. **The candidate universe is 68 places, not 3508** — 50 routable cafés/museums with hardcoded 7–22 hours and 0 cost. The whole "verified catalog" is a facade in local/mock mode.
3. **The seed rotation deterministically deprioritizes the best intent match** — the night market is #1 by intent score yet is pushed from index 0 to index 19 (probe 4); relevance is a lottery ticket per session.
4. **"Phố cổ Hà Nội" resolves to "Phở hà nội"** — the LLM path can turn an iconic district into a noodle shop, and its resolved places bypass both `is_routable` and `validate_plan`'s hour checks.
5. **The test suite asserts the bugs** — `test_pipeline.py:81-93` demands all four anchors, `:96-109` passes only via a seed-dependent OR, and the suite cannot even import on Python 3.10 without a `datetime.UTC` shim.

## 15. Confidence and ground-truth tally

**Confidence: 6/10.**

Reasoning: Every load-bearing claim in this report rests on code I read and then *ran* (full `build_plan` outputs, replicated sort/rotation arithmetic, catalog statistics, test suite execution). The verdict ("does not work in mock; cannot beat a plain LLM structurally") is not speculative. The rating is capped at 6 rather than higher for three honest reasons: (1) I could not exercise the real groq/deepseek path (no API key) — the LLM-mode findings (7) are strong code-reading inferences but not live-run; (2) the rotation's per-session lottery means some *specific* user-visible outcomes (e.g., "market at 19:55 on day 2" in one seed) actually look fine, so the failure is distributional rather than absolute; (3) I did not run the full multi-lane red-team, so cross-lane interactions (swipe/refine share-button behavior) were intentionally not double-checked.

**Ground-truth tally:** of the ~10 load-bearing conclusions in this report, **8 are externally verified by executed probes** (folding outputs, build_plan schedules, rotation arithmetic, catalog counts, catalog-match resolutions, scheduler simulation, determinism, frontend regex). The remaining **2 rest on model judgment**: the *semantic* claim that "Hồ Gươm forced into a coffee request is a defect" (the codebase's own tests call it desired), and the *real-mode* LLM-path degradation (code-read, not live). Headline confidence is set to 6/10 consistent with that 8/10-verified ratio and the known mock-only runtime.

---

*Research only — no source code was modified. All probes reproduced in `C:\Users\Admin\AppData\Local\Temp\opencode\probe{1..5}.py`.*
