# User-Interaction Gap Analysis — "Mình Đi Đâu Thế" vs layla.ai-class conversational planners

**Lane:** UX / user-interaction gap analysis
**Grounded in:** `PlanView.tsx`, `Planner.tsx`, `MapView.tsx`, `page.tsx`, `explore/page.tsx`, `history/page.tsx`, `settings/page.tsx`, `login/page.tsx`, `roadtrip/page.tsx`, `Layout/Navigation`, `i18n` copy (vi + en), `PARITY_MATRIX.md`, `api.ts`, `session.ts`.
**Method:** Read the user-facing surface end to end; judged interactions against best-practice patterns for conversational AI trip planners. This lane deliberately avoids code-level duplication (frontend/backend lanes cover those). Severity = High (blocks the core value loop), Medium (degrades a core loop), Low (polish), Note (narrow/enhancement).

---

## 1. User-journey gap inventory per stage

### Stage 1 — Arrival & onboarding (first visit, no login, no plan)

**What exists today.** A single marketing hero (`/`): headline, tagline, a `Planner` widget embedded in the hero, three featured "idea" cards, three "how it works" steps, three FAQs, and a CTA banner. The planner widget shows a welcome bubble, three idea chips (coffee / food / culture), one free-text field, and a "số người" (people count) field. No login wall — generation works anonymously via a device session.

**Gap 1.1 — No guided first-run; the form is a blank canvas with a tiny typeahead-style box.**
**Severity: Medium.**
The whole generation model is "type one sentence, we return exactly one plan." A first-time user (persona: busy Vietnamese weekend planner, often on mobile, low tolerance for long text entry) sees a large empty input and a welcome bubble. There is no step-by-step intake (destination → dates → people → vibe → budget), no suggested starter sentences beyond three chips, and no "what we'll ask" preview. Layla-class products reduce the first prompt to the absolute minimum and then *ask follow-up questions conversationally*; here the system instead tries to guess duration from the free text via a regex (`Planner.tsx` `inferDuration`) and silently defaults everything else.
**User-visible impact:** A user who types "đi chơi cuối tuần" gets a plan whose duration/budget/people they never explicitly set. If the regex misses the phrase, duration silently falls back to `ca_ngay` (full day). The user believes they asked for a specific thing; the plan may contradict it, with no way to see what was inferred.
**Done looks like:** A 3–4 field intake (destination + dates/opens, people, budget band, vibe chips) *plus* free text; every silent default becomes an explicit, visible, confirmable input. First-run sees the welcome bubble offering "ask me anything" examples that fill the box when tapped.

**Gap 1.2 — Duration is invisible and regex-guessed; the duration selector UI exists in i18n but is never rendered.**
**Severity: High.**
`plannerTranslationKeys` includes `durationLabel`, `fewHours`, `halfDay`, `fullDay`, `multiDay`, but `Planner.tsx` never renders them — only the people input is shown. Duration is derived from `inferDuration()`, which matches a *hard-coded* list of Vietnamese/English phrases ("2 ngày", "nửa ngày", "cuối tuần", "few hours", …). Anything outside that list (e.g., "đi từ thứ 7 đến chủ nhật", "3 ngày 2 đêm", "tối thứ sáu") silently defaults.
**User-visible impact:** The single most important planning dimension (how long) is the one dimension the user cannot directly set. A "nửa ngày" request that the regex misses becomes a full-day plan — the user gets a plan that ignores what they said, and nothing on screen tells them why.
**Done looks like:** A visible duration control (segmented buttons) that is pre-filled from the text and always editable, plus the backend trusting the explicit value over the regex.

**Gap 1.3 — Budget is hardcoded and invisible.**
**Severity: High.**
`Planner.tsx` sends `ngan_sach: 1000000` (1,000,000 VND) with no input field anywhere in the onboarding. The plan view shows only `chi_phi_moi_nguoi` (cost/person) after the fact. Budget is the #1 planning constraint for the target persona (weekend, young couples/friends, budget-conscious) and the app both (a) never asks for it and (b) never discloses that it assumed 1M VND.
**User-visible impact:** A student couple whose real budget is 400k/person gets a plan full of places out of their range and a per-person total they can't afford — with no obvious "make it cheaper" control beyond one chat chip. Layla asks budget explicitly and reflects it in the plan.
**Done looks like:** A budget-band selector at intake (e.g., "<300k / 300–700k / 700k–1.5M / >1.5M per person, or 'no limit'"), echoed into the plan header ("Budget: ~700k/person · 2 people"), and used as a chip-driven refinement.

**Gap 1.4 — Featured cards don't prefill; they just focus the input.**
**Severity: Low.**
The three "featured" destination cards and the CTA call `preventDefault()` and `focus()` the planner input (`page.tsx:54,103`). Tapping "Cà phê và đi bộ cuối tuần" neither fills the box nor starts planning — it just moves the cursor. The chips inside the planner *do* set the text, so the behavior is inconsistent across nearly identical affordances.
**User-visible impact:** A user taps an attractive card expecting the promised trip; nothing visibly happens. Feels broken, causes drop-off.
**Done looks like:** Tapping a featured card sets the input value to that idea *and* scrolls/focuses the planner, or navigates to the plan flow directly. (One line per card.)

**Gap 1.5 — No "sign in to keep your trip" nudge at the exact moment of value.**
**Severity: Medium.**
Login exists (Google OAuth, `login/page.tsx`) and anonymous plans are device-bound to `ma_phien`. But there is no prompt to sign in after a plan is generated, no "your plan is saved only on this device" warning on the plan page, and no account toggle in the workspace header. The FAQ mentions persistence, but the user has to go find it.
**User-visible impact:** Anonymous users who clear cookies or switch devices silently lose access to their trips; they only discover it when the History page is empty. Layla-class products treat "save" as frictionless and surface an upsell at the moment of completion.
**Done looks like:** A dismissible "🔒 This plan is saved on this device only — sign in to keep it on any device" bar on the plan page for anonymous sessions, plus a one-tap sign-in from the share dialog.

**Gap 1.6 — No location/destination selection in the core planner.**
**Severity: Medium.**
The planner hardcodes Hanoi (`location: {lat:21.0285, lng:105.8542}` in `Planner.tsx:105-106`). The brand is "Mình Đi Đâu Thế" (Where shall we go?), so a Hanoi default is defensible, but there is no destination field, no "plan somewhere else" affordance, and the landing copy never tells users this is Hanoi-only. (The `roadtrip` page exists for multi-city, but it's a separate, form-heavy tool, not part of the conversational flow.)
**User-visible impact:** Users who come in expecting to plan Da Nang or Saigon can't; they must discover the roadtrip page. For a product named "where do we go", destination ambiguity is a positioning-level miss.
**Done looks like:** A destination chip row in the planner ("Hà Nội · Đà Nẵng · Sài Gòn…") or an explicit "planning for Hanoi" hint in the welcome bubble.

---

### Stage 2 — Planning session (the core conversation)

**What exists today.** After generation, the user lands on `PlanView`. A left "Trợ lý chuyến đi" (Trip assistant) panel holds: a single `assistantWelcome` bubble, three quick-refine chips ("Rẻ hơn", "Ít di chuyển", "Thêm cafe"), and a free-text chat box whose placeholder literally invites commands ("Ví dụ: đổi điểm này"). Each slot card in the timeline has a "↻" swap button. `Versions` + `restore` give undo.

**Gap 2.1 — The "chat" is a command bar, not a conversation.**
**Severity: High — this is the defining gap vs layla.ai.**
The assistant never replies with language. `parseReplyKey()` (`PlanView.tsx:26`) accepts exactly two reply keys — `swipeSuccess` or `assistantWelcome` — and `applyRefine` appends whichever one came back. Every refinement — "rẻ hơn", "thêm điểm X", "đổi ngày" — is answered with the *same* canned bubble: "Đã thay đúng một điểm và kiểm tra lại lịch trình." There is no natural-language acknowledgment, no clarification question ("Bạn muốn tiết kiệm đến mức nào?"), no "here's what I changed and why", no counter-suggestion, no follow-up probe.
**User-visible impact:** The user is in a "chat" but gets no dialogue. They ask for something and see a terse, generic success line whose copy literally describes replacing one place ("thay đúng một điểm") even when they asked to change budget or pace. This breaks the illusion of an intelligent agent, forces users to re-read the plan to detect changes, and leaves constraint changes unverified. Layla's core loop is a real back-and-forth; this is the single biggest feel-gap.
**Done looks like:** The backend returns a short natural-language reply (Vietnamese) summarizing what changed and offering 1–3 next-step chips; the chat panel renders a real threaded conversation (user turns + assistant turns), scrolls, and persists per plan. Copy must be dynamic, not a fixed key.

**Gap 2.2 — Constraints are never confirmed back to the user ("no echo").**
**Severity: High.**
There is no place in the workspace that states the active planning constraints: number of people, budget, duration, vibe/style, pace. `trip-facts` shows weather, cost/person, and place count — nothing about *what the system believes the user asked for*. After a refine, no summary like "Đã áp dụng: ngân sách ~500k/người, 2 người, đổi 3 điểm" appears.
**User-visible impact:** Every turn starts a guess-the-intent game. The user can't tell if the system heard them ("I asked for cheaper — did it actually lower the per-person total?"), so they repeat themselves or give up. This is a *trust* gap as much as an interaction gap.
**Done looks like:** A persistent "constraints strip" (budget band, people, duration, style, pace) above the itinerary, editable inline and via chat; every assistant reply confirms the delta ("Giảm ngân sách còn ~500k/người · đã thay 3 điểm để vừa túi tiền").

**Gap 2.3 — Budget/style/pace cannot be changed mid-session with visible effect.**
**Severity: High.**
The refine request body is only `{message, phien_ban, dia_diem_dang_chon}`. If the user says "rẻ hơn", the system has no budget parameter to move — the plan hardcoded 1M at creation, and there's no way to tell how the refine is interpreted. There's also no pace control (relaxed vs packed) and no style control beyond whatever the chat prompt happens to convey.
**User-visible impact:** The user's most common real-world requests ("make it cheaper", "we have kids", "we move slowly", "too rushed") become coin flips. Layla handles these as first-class, confirmable constraints.
**Done looks like:** Structured refinement — chips that set budget/pace/style and produce a plan diff, with the constraint strip updating in the same turn.

**Gap 2.4 — No undo/redo for a chat refine; restore is a hidden drawer with no diff.**
**Severity: Medium.**
Version history exists and `restore` works, but it's buried in a header button ("Phiên bản 3"), opens a drawer listing version numbers + reasons, and offers *no diff* — the user can't see what changed between versions before restoring. After a refine they dislike, there's no inline "↩ hoàn tác" (undo) button in the chat; they must know to open Versions and restore blind.
**User-visible impact:** Fear of breaking a good plan suppresses experimentation (the exact behavior a planner should encourage). Users stop asking for changes because they can't easily reverse them.
**Done looks like:** A per-turn "Hoàn tác" button on each assistant bubble that restores the prior version; the version drawer shows a compact before/after diff (added/removed places, cost delta) so restore is informed.

**Gap 2.5 — One-shot actions with no agency: swap and regenerate give the user no choice.**
**Severity: Medium.**
The "↻" swap (`swipe`) replaces the selected place with *a* replacement chosen by the backend — the user has no say in *which* alternative, no "see 3 options" picker. Same for "Làm lại" (regenerate): it overwrites the plan and dumps a `swipeSuccess` bubble into the chat. Layla-grade interaction lets you browse 2–3 alternative candidates and pick.
**User-visible impact:** Replacing a disliked spot feels like Russian roulette — the swap could be worse, and there's no way to pick the best of several. Regenerate is destructive-feeling (only version history saves you).
**Done looks like:** Swap opens a mini-sheet with 3 candidate alternatives (name, price, travel time from neighbors, mini-photo); the chat reads as a decision log.

**Gap 2.6 — Refine has no live status/typing affordance.**
**Severity: Low.**
The workspace shows a generic `busy` line ("Đang xử lý…") during a refine, but with no progress steps (unlike the *creation* flow, which streams "Đang tìm địa điểm…", "Đang xếp tuyến…" via SSE). A 10–30s refine looks frozen.
**User-visible impact:** Users assume it hung and re-submit or leave. Creation already proves the app *can* stream status — reuse it for refine.
**Done looks like:** Refine reuses the SSE status stream (`findingPlaces`/`routingPlan`-style messages) in the chat panel.

**Gap 2.7 — Chat history is ephemeral; reloading wipes the conversation.**
**Severity: Low.**
`conversation` is `useState` in-memory, reset to a single `assistantWelcome` on every reload/mount (`PlanView.tsx:92`). The *plan* persists, but the user's whole negotiation history (what they asked, what changed, version chain narrative) disappears on refresh.
**User-visible impact:** Returning to a plan means re-discovering what was agreed. For a multi-day trip refined across several sessions, this is disorienting.
**Done looks like:** Conversation + version entries rendered from persisted data (backend or `offline-plan:${token}` snapshot) so reloads restore the dialogue.

---

### Stage 3 — Reviewing the plan

**What exists today.** Day-tab bar, per-slot timeline (photo, index, times, description, cost, note, source link, swap button), synchronized Leaflet map with numbered markers, route polyline, and popup photos. Strong map↔timeline selection sync in both directions. Trip facts row (weather, cost/person, place count). Export: PDF, ICS, JSON.

**Gap 3.1 — No day-by-day *overview*; you can only ever see one day.**
**Severity: Medium.**
The day tabs switch the entire timeline; there's no condensed multi-day overview (Layla-style "Day 1 · 5 places · 12km · lunch at X" strip), no day cost totals, no "which day is packed vs light" signal.
**User-visible impact:** For multi-day plans the user can't sanity-check the trip at a glance; they must click through every day to feel the shape of the trip.
**Done looks like:** A scrollable day-summary strip above the tabs (per day: place count, walking time, cost, highlighted busiest day) that jumps to that day's timeline.

**Gap 3.2 — No direct editing of the plan: reorder, time, notes, add-a-place are all chat-only.**
**Severity: High.**
There is no drag-and-drop reorder of slots, no inline time/note editor, no "add a place to this gap" affordance. Every edit must be expressed as a chat prompt, and chat can't always express positional edits ("move coffee shop after the temple") reliably. The `ghi_chu` (note) and times are read-only display values.
**User-visible impact:** Users who want to nudge one thing (swap two stops, push lunch back an hour, add a note) have no direct manipulation surface. Layla-class itinerary editors make these one-drag operations. Chat-only editing makes the tool feel like a "generate once, read forever" PDF rather than a living document.
**Done looks like:** Drag-handles on slots with on-drop re-route; inline time steppers; an "add place here" (+) between slots that opens a small search. Chat remains for intent-level changes; direct manipulation covers mechanical ones.

**Gap 3.3 — No "what if" / comparison surface.**
**Severity: Medium.**
The only comparison mechanism is version history (blind restore). There is no way to ask "what if I skip the Old Quarter?" and see the plan side-by-side with the current one, or to keep a draft while trying an alternative.
**User-visible impact:** The core planning behavior — trying variants — is punishing (destructive + hard to revert). Layla keeps the conversation as a living negotiation; here each variant is a fork you must manage manually.
**Done looks like:** Refine/regenerate produces a "new version" badge in the chat with an inline diff and a "giữ bản này / quay lại bản cũ" choice; side-by-side compare of two versions.

**Gap 3.4 — Map is read-only: no route editing, no click-to-slot jump for far markers, no day boundary on map.**
**Severity: Low.**
The map shows the active day only, fit-bounds to its points, and syncs selection. But it can't act as an editor (drag a pin to reorder, click the polyline to see transit info), and there's no transit-time info between stops anywhere in the UI (the route is drawn but never explained).
**User-visible impact:** Users can't answer "how long is the hop from A to B?" without leaving the app. For a route-optimization product, transit time is the headline claim — show it.
**Done looks like:** Clicking the polyline between two markers shows "~12 phút đi bộ"; slot cards show "→ next stop ~8 min"; map supports tap-to-select and day-pin coloring.

**Gap 3.5 — No accommodation/meal anchoring in the plan structure.**
**Severity: Note.**
The plan is place-and-time only; there's no hotel anchor, no breakfast/lunch/dinner markers, no "stay here, eat there" narrative. The explore/roadtrip pages have hotels/flights/transfers, but they never merge into the itinerary view.
**User-visible impact:** Multi-day plans feel like a list of points, not a trip with a home base. Layla structures days around where you sleep and eat.
**Done looks like:** A "nơi ở" card per day + meal slots; hotel from Explore becomes a plan anchor.

**Gap 3.6 — Long plans are one long vertical scroll; no search/filter within the itinerary.**
**Severity: Low.**
A 10-stop day or a 30-day plan is an unbroken timeline with no way to find "the phở place" or filter "only food" or "only free".
**User-visible impact:** Reviewing a big plan is exhausting; users skim and miss things.
**Done looks like:** A per-day filter row (Tất cả / Đồ ăn / Văn hóa / Miễn phí) and an in-plan search box.

---

### Stage 4 — Personalization depth

**What exists today.** Intake collects: free text, people count (2–30). Settings: language (19 locales), currency (7), units (metric/imperial). Cost/person is displayed. That is the entire personalization surface.

**Gap 4.1 — Style, pace, mobility, dietary, and travel-party profile are never captured.**
**Severity: High.**
There is no notion of travel style (foodie / culture / adventure / chill), pace (relaxed vs packed), companions (couple, family with kids, group of friends, elderly parent), mobility, or dietary needs. The three vibe chips are the only gesture toward this, and they're just text prefixes.
**User-visible impact:** The app produces one "generic balanced" plan for everyone. A family with a toddler and an elderly grandparent gets the same itinerary as two 25-year-olds. Layla's value is precisely that it *asks and remembers* these.
**Done looks like:** A 60-second companion profile (or conversational follow-ups): "Bạn đi với ai?" (cặp đôi / gia đình / nhóm / một mình), "Bạn thích nhịp độ nào?" (thong thả / cân bằng / dày đặc), "Có trẻ nhỏ hay người lớn tuổi không?". Profile stored in preferences and reflected in plan generation + constraint strip.

**Gap 4.2 — Preferences exist in settings but barely reach the experience.**
**Severity: Medium.**
Settings can set currency and units, but per `PARITY_MATRIX` the plan cost is *always rendered in VND* ("chi phí plan vẫn hiển thị VND để không giả tỷ giá") — so a user who sets USD sees the currency change only in the Explore page, not in their plans. Units change only the temperature display. There's no visible "we're using your profile" feedback.
**User-visible impact:** The settings screen feels decorative; personalization doesn't produce a perceivable difference where it matters (prices in the plan).
**Done looks like:** Plan prices display in the chosen currency (with a clear "≈, estimated at live rate" note) or the app honestly labels currency as Explore-only. Better: preferences drive the constraint strip and the planner pre-fills.

**Gap 4.3 — No "learns from you" loop across trips.**
**Severity: Medium.**
Feedback is stored and acknowledged ("đã được lưu cho lần lập kế hoạch sau"), but there is no visible mechanism for the next plan to reflect past feedback or past trips (no "based on your last trip to Hanoi…"). Nothing on the home page or planner indicates the system remembers you.
**User-visible impact:** "We saved your feedback for next time" is a promise the UI can't demonstrate being kept. Personalization feels like a lie until it's visible.
**Done looks like:** On a returning anonymous session (or signed-in account), the planner pre-fills profile chips and shows "Dựa trên chuyến trước của bạn, mình đã ưu tiên quán cà phê có chỗ ngồi thoáng." — at minimum, show past trip titles on the home page.

---

### Stage 5 — Persistence & resume

**What exists today.** Anonymous plans saved server-side by `ma_phien` (device session), listed in `/history` via `X-Session-Id` (no login needed). Offline snapshot in `localStorage` (`offline-plan:${token}`) plus service-worker caching. Google OAuth for cross-device sync. In-app 24h-before-trip notifications inbox on History. PDF/ICS/JSON export.

**Gap 5.1 — No resume path from the home page; returning users hit a wall of marketing.**
**Severity: High.**
The home page is static marketing + planner. A returning user with three saved plans sees the exact same hero, zero "continue planning" affordance, and no evidence their trips exist until they notice the "Chuyến đi" nav item. There's no "welcome back", no recently-viewed list, no "resume" button.
**User-visible impact:** The app doesn't feel like *their* app on return; momentum from the previous session is lost. Layla-class products greet returning users with their trips.
**Done looks like:** A "Tiếp tục chuyến đi" section on `/` for sessions with plans (3 most recent, with title, date, "Tiếp tục tinh chỉnh"), plus a one-tap continue from the nav badge. Cheap to build — the data already exists in `/api/plans`.

**Gap 5.2 — History is a bare list with no metadata, search, or lifecycle actions.**
**Severity: Medium.**
`history/page.tsx` renders each trip as title + summary + link. No trip dates, no last-modified, no search/filter, no rename, no duplicate ("make a similar trip"), no delete/archive (delete exists only as full account deletion in Settings, and requires the phrase "XOA TAI KHOAN").
**User-visible impact:** As trip count grows the list becomes unusable; users can't find "the Da Lat plan from last month" and can't clean up. No rebooking loop either.
**Done looks like:** History cards with dates + day count + cost, searchable, with rename/duplicate/archive actions; a "copy and adjust" that opens the planner pre-filled from an existing plan.

**Gap 5.3 — Return-visit restore of a session can silently strand plans on the old device.**
**Severity: Low.**
Plans are tied to `ma_phien` in localStorage. Clearing site data, switching browsers, or using a different device without login orphans the trips. There's no "sign in to sync" prompt and no cross-device pick-up of the anonymous session via a share link.
**User-visible impact:** The classic "my plans disappeared" complaint — but it's avoidable because share links are long-lived read-only URLs.
**Done looks like:** Sign-in nudge (Gap 1.5) plus "open shared link → claim this trip into your account" affordance on plan pages for anonymous viewers.

---

### Stage 6 — Social / sharing

**What exists today.** Share button → native share sheet or copied read-only URL (`/plan/{token}`). Comments panel ("Trao đổi cùng nhóm"): display name + message, owner can resolve/reopen. Owner-only resolve; version restore is owner-only. PARITY_MATRIX claims "read-only share, comments, owner-only resolve."

**Gap 6.1 — Collaboration is write-comments-only; there's no shared editing, voting, or "plan together".**
**Severity: Medium.**
A trip shared with a partner/friends is read-only for them — they can comment ("Tớ thích quán này") but cannot tap to swap a place or vote on alternatives. In a product whose use case is literally "Mình đi đâu thế?" (a *group* question), the group can talk but not act together.
**User-visible impact:** The social loop is comment-debate-then-text-the-owner-to-change-it. Layla-class and Google-docs-era expectations are "everyone edits the same plan".
**Done looks like:** Shared plans allow guests to suggest swaps ("đề xuất đổi điểm này") that create pending suggestions the owner approves/rejects — visible in the comments feed as actionable items. Real-time presence is a later-phase win.

**Gap 6.2 — No share-as-image / PDF-as-share / social cards; sharing = a URL with a title.**
**Severity: Low.**
Native share and copy-link carry `title` + `tom_tat`, but there is no auto-generated trip summary image (a staple of layla-class sharing on Zalo/Messenger, where link previews often don't render rich cards).
**User-visible impact:** Shared plans look like plain links in chat; recipients don't see the beautiful plan, so sharing doesn't drive adoption.
**Done looks like:** An auto-generated share card (day-by-day one-pager image) + "tải ảnh tóm tắt" button; OpenGraph tags on `/plan/{token}`.

**Gap 6.3 — Comments have no presence/threading/notifications.**
**Severity: Low.**
No notifications when someone comments on your shared plan (only the owner sees a badge count on the header button while on the page). No threaded replies, no emoji reactions, no "was this resolved?" status surfaced to the group.
**User-visible impact:** Group discussion is fire-and-forget; the owner must keep reloading the page to see replies.
**Done looks like:** Notify the owner of new comments (in-app inbox that already exists for reminders); allow @mentions; thread replies under comments.

---

### Stage 7 — Trust & transparency

**What exists today.** Per-slot source links (`nguon_url`/`nguon`), weather and cost disclaimers, "verified catalog, no fabricated places" FAQ/hero copy, Explore provenance (provider, fetched/expires, price analysis, provider-confirmation disclaimer), honest "we never confirm bookings" language, "system does not self-confirm" copy. This is genuinely a strength.

**Gap 7.1 — No "why this suggestion" reasoning at the place level.**
**Severity: High (perceived trust).**
Each slot shows name, description, cost, source — but never *why it was chosen* ("gần quán cà phê bạn chọn, trong ngân sách, mở cửa đúng giờ", or "vì bạn nói thích yên tĩnh"). The assistant welcome bubble claims it arranged things "around travel time, opening hours, and budget", but nothing in the plan makes that visible per place.
**User-visible impact:** Users can't tell if the plan is intelligent or random; every suggestion is an unearned assertion. Layla's conversational replies carry the reasoning, which is *the* trust mechanism for AI planning.
**Done looks like:** Each slot (or each day's header) carries a one-line rationale; the chat's post-refine reply states reasons ("Mình đổi Nhà thờ Lớn → Chùa Trấn Quốc vì gần tuyến xe buýt và giảm 20 phút di chuyển").

**Gap 7.2 — Pricing shown as a single per-person estimate with no breakdown or live tie-in.**
**Severity: Medium.**
The plan shows a total `chi_phi_moi_nguoi` and per-slot `chi_phi`, both "estimates", with a generic disclaimer. There's no per-category breakdown (food vs tickets vs transport), no price range per place, and no "book this in Explore at live price" linkage from a plan slot to the live inventory screens that the app already has.
**User-visible impact:** The budget claim is unverifiable and un-actionable. Users can't say "transport is eating my budget".
**Done looks like:** A cost breakdown card (entry/tickets, food, transport, misc) with "≈" labels, and per-slot "check live price" affordance that jumps to Explore pre-filtered.

**Gap 7.3 — No disclosure of AI vs algorithmic generation inside the workspace.**
**Severity: Low.**
The landing page and FAQ explain "AI helps choose and route; catalog is verified" — good. But inside the plan view there's nothing saying what was AI-generated vs catalog-sourced vs estimated, and the `dataNotice` on the planner ("AI trả phí chỉ bật khi admin cấu hình provider") is developer-facing phrasing leaking into the consumer surface.
**User-visible impact:** A savvy user sees half-Vietnamese/half-technical copy (`dataNotice` is literally untranslated Vietnamese leaking into all 19 locales — see the en/ar/… rows) and loses confidence.
**Done looks like:** Consumer-grade disclosure in the workspace footer ("Địa điểm từ danh mục đã kiểm chứng · chi phí là ước tính · tuyến do thuật toán xếp") and proper translation of `dataNotice`.

**Gap 7.4 — Broken image handling is silent (falls back to no photo, no message).**
**Severity: Low.**
`brokenImages` hides a slot's photo on error with no placeholder or note. If catalog images break, plans look unpolished and "hallucinated".
**User-visible impact:** Visual trust erodes; a plan full of empty image slots reads as low-quality data.
**Done looks like:** A graceful placeholder (category icon) so the timeline always looks designed.

---

### Stage 8 — Closing loops

**What exists today.** Post-trip feedback form (rating 1–5 + text) appears once the trip date is in the past (`canFeedback = isPastUtcDate(plan.ngay_di)`), owner-only. In-app 24-hour-before-trip reminder notifications inbox on History. Version history retained. That's the complete closing surface.

**Gap 8.1 — The trip lifecycle after creation is dead air until 24h before departure.**
**Severity: Medium.**
Between "plan created" and "T-24h", nothing happens: no confirmation the plan is saved, no packing/checklist, no weather-refresh nudge if conditions change, no "day 1 is in 3 days" cadence. The 24h reminder is the *only* touchpoint.
**User-visible impact:** The product exists as a burst (plan → forget → one reminder) rather than a companion. Layla-class products hold attention across the planning-to-travel arc.
**Done looks like:** A lightweight trip dashboard per plan ("Còn 12 ngày nữa · Thời tiết có thể mưa chiều thứ 7 — xem lại lịch"), plus optional email reminders (out of scope for now given no email infra, but in-app is cheap).

**Gap 8.2 — Feedback is one-shot and owner-only; no trip mates' voices, no "did this help" in-session.**
**Severity: Low.**
Only the owner can rate after the trip; comments are the only channel for companions. There's no lightweight in-session "Was this helpful?" micro-feedback that would power a learning loop.
**User-visible impact:** The feedback loop undercounts the group, and nothing before trip-end shapes the experience.
**Done looks like:** Post-trip feedback prompt to share the link with the group ("Chia sẻ để cả nhóm đánh giá"), and a per-day "hữu ích?" inline thumbs.

**Gap 8.3 — No rebooking / "plan this again" loop.**
**Severity: Low.**
After a successful trip, there's no "plan a similar trip", "visit again with adjustments", or seasonal variant. Retention depends on the user remembering to return.
**User-visible impact:** A one-and-done product; no compounding value.
**Done looks like:** A "Tạo chuyến tương tự" button in history that clones the plan into a new planner session (pre-filled) for the next weekend.

---

## 2. Prioritized "UX impact vs effort" matrix

Ranked by (user-visible impact × probability) / (implementation effort). These are the 7 gaps to fix first.

| # | Gap | Stage | Severity | Impact (1–5) | Effort (1–5, 5=expensive) | Priority |
|---|---|---|---|---|---|---|
| 1 | **Make the workspace chat a real conversation** (dynamic replies + threaded history) (2.1) | 2 | High | 5 | 3 | **Fix first** — this is the product's identity; currently a command bar wearing a chat costume |
| 2 | **Echo constraints back** — visible budget/pax/duration/style strip + confirm in every reply (2.2, 2.3, 4.1) | 2,4 | High | 5 | 3 | **Fix first** — unlocks trust and the biggest perceived intelligence leap |
| 3 | **Ask budget + duration explicitly at intake** (1.2, 1.3) | 1 | High | 4 | 1 | **Fix first** — tiny, mostly UI; kills the "silent defaults" trust killer |
| 4 | **Undo per refine + diff-aware version restore** (2.4) | 2 | Medium | 4 | 2 | **Fix first** — cheap, removes the "editing is risky" friction |
| 5 | **Resume/continue planning on home for returning users** (5.1) | 5 | High | 4 | 1 | **Fix first** — data already exists; pure frontend |
| 6 | **Direct manipulation of the itinerary** (reorder/time/insert) (3.2) | 3 | High | 4 | 4 | **Second wave** — bigger build (needs re-route endpoint per edit), but transforms "read-only PDF" feel |
| 7 | **Per-place "why" rationale + live-price tie-in** (7.1, 7.2) | 7 | High/Med | 4 | 3 | **Second wave** — trust compounding; piggybacks on existing source data |
| 8 | **Returning-user sign-in nudge + group suggestion workflow** (1.5, 6.1) | 1,6 | Med | 3 | 2 | **Second wave** — retention + the group use-case |

**Quick wins (see §3) not listed but highest ROI:** budget/duration intake fields (item 3 above), featured-card prefill, home resume list (item 5), swap-with-options sheet, version diff, transit-time labels, share card image.

---

## 3. Quick wins (small code change, big feel change)

1. **Add budget-band + duration segmented controls to the planner** and stop hardcoding `ngan_sach: 1000000` / stop trusting only the regex. ~1 day. Biggest trust win per hour.
2. **Make featured cards and CTA actually fill the planner input** (`setContext(idea)`) instead of just focusing it. A few lines (`page.tsx`).
3. **Resume list on the home page**: fetch `/api/plans` (already done in History) and show 3 "Tiếp tục chuyến đi" cards. Pure frontend, reuses existing endpoint.
4. **Constraint strip above the itinerary** (`👥 2 · 💰 ~1M/người · ⏱ cả ngày · 🏃 cân bằng`) fed from the create/refine inputs. Reuses data already in state; the app never surfaces what it "knows".
5. **Replace the fixed `swipeSuccess` bubble copy** with a reply that at least echoes the user's own text ("Đã áp dụng: {message} — xem lại lịch trình nhé") so the chat acknowledges what was asked. One copy/param change; removes the biggest "it ignored me" feeling while the real reply engine is built.
6. **Per-turn undo button in the chat** wired to the existing version/restore API. Frontend only.
7. **Show transit time between stops** ("→ 12 phút đi bộ") on slot cards and on the map polyline. Data likely already computed by the routing layer.
8. **Swap-with-options sheet**: return 3 candidate replacements in `swipe` and let the user pick. Backend change but bounded; huge agency win.
9. **Version diff view**: compute added/removed place names + cost delta between consecutive versions in the drawer. Client-side diff over plans already fetched.
10. **Fix `dataNotice` leakage**: translate it per-locale (it currently shows Vietnamese in all 19 locales). A copy fix; visible proof of polish on every market.
11. **Auto-generated share image / OpenGraph** tags on `/plan/{token}` so Zalo/Messenger links render a rich card.
12. **Per-day cost total** in the trip facts / day tab ("Ngày 1 · ~350k · 6 điểm · 4.2km đi bộ"). Client-side sum of existing slot costs.

---

## 4. Executive summary

**"Mình Đi Đâu Thế" has a solid single-shot product core** — verified catalog, optimized routing, a genuinely synchronized map↔timeline, honest source/provenance disclosure, offline resilience, version restore, and 19-locale copy. **But it is a "generate one plan, read it, export it" tool, not a conversational trip planner.** The defining gap is that the workspace chat is a command bar: the assistant never replies with language, never confirms constraints, and never explains choices — every refinement is answered by one canned bubble ("Đã thay đúng một điểm") even when the request was about budget or pace. Budget and duration are never asked (hardcoded 1M VND, regex-guessed duration), returning users get no resume path on the home page, plans can't be edited directly (drag/time/insert are chat-only), and restore is blind (no diff). The fix order is clear and cheap at the front: make the chat reply in natural language and echo constraints, ask budget/duration explicitly, add per-refine undo, and surface "continue your trips" on return. Those five changes alone — before any deeper personalization, collaboration, or lifecycle work — will move the product from "a clever itinerary generator" to "an assistant that plans with you."

**Confidence: 8/10** — heavily grounded in direct code reading of the entire user-facing surface.

**Ground-truth tally (verified by reading code vs model judgment):**
- Verified in code (ground truth): assistant replies only `swipeSuccess`/`assistantWelcome` (`PlanView.tsx:26,102`); budget hardcoded 1,000,000 (`Planner.tsx:108`); location hardcoded Hanoi (`Planner.tsx:105`); duration regex-guessed with silent `ca_ngay` default (`Planner.tsx:65-72`); duration UI keys exist but are never rendered; featured cards only `focus()` (`page.tsx:54,103`); no constraint display in `trip-facts`; chat state resets on reload (`PlanView.tsx:92`); history shows title+summary only; home page has no resume section; comments are text-only; `dataNotice` leaks untranslated Vietnamese into all locales; Explore shows provenance/expiry/price-analysis; feedback gated on past trip date; 24h reminder inbox exists in History.
- Model judgment (not directly verifiable from code alone): relative priority ordering, effort estimates, layla.ai interaction patterns (grounded only via PARITY_MATRIX references; external research lane owns live layla.ai behavior verification).
