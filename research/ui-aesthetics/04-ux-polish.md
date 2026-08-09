# 04 — UX Polish: Motion, States, A11y, RTL (Mình Đi Đâu Thế)

> Phạm vi: chất lượng tương tác & polish — motion/transition, trạng thái (loading/empty/error/success), status/toast, accessibility visual, RTL/i18n visual, scroll & sticky, skeleton.
> Chỉ đọc, không sửa code. Nguồn chính: `frontend/app/globals.css`, `components/*.tsx`, `app/layout.tsx`, `lib/i18n-core.ts`, `lib/workspace-translations.ts`.

---

## Tóm tắt điều hành

Toàn cục hệ thống có một nền tảng chuyển động **nhất quán và tinh tế hiếm thấy** ở tầng styling: một easing duy nhất `--ease: cubic-bezier(.4,0,.2,1)` được dùng cho **mọi** transition, dải duration chuẩn (transform .12s / màu + shadow .2s), hierarchy hover rõ ràng (nút −1px, card −4px, icon scale 1.06→.94). `prefers-reduced-motion` được xử lý bằng override toàn cục. Đây là điểm mạnh cốt lõi.

Nhưng phần **trạng thái động (dynamic states) lại yếu nhất trong toàn bộ nguồn**: mọi "đang xử lý" chỉ là một dòng text màu accent; **không có spinner, không skeleton, không typing-bubble** dù CSS cho typingPulse và shimmer đã được viết sẵn (dead code — chưa bao giờ render). Nghiêm trọng hơn, trong `PlanView`, **mọi message kể cả lỗi đều render bằng class `.status` màu accent** thay vì `.error` màu đỏ, làm cho "thành công", "đang chạy" và "thất bại" trông giống hệt nhau — điều này mâu thuẫn trực tiếp với các trang còn lại (Planner/Explore/Settings) vốn làm đúng.

Accessibility visual có 2 lỗi contrast đáng kể: (1) **nút Danger ở dark mode** = nền hồng nhạt `#ff9b8a` + chữ trắng → ~2.0:1, không đọc được; (2) hệ màu xám `--muted`/`--muted-2` ở light mode dưới ngưỡng AA 4.5:1 cho text nhỏ (13–15px). RTL là mảng "cài đặt nửa vời": `dir="rtl"` được gán ở client nhưng không có một selector `[dir=rtl]` nào trong CSS, cộng với hàng loạt `margin-left/right`, `translateX(2px)`, `text-align:left`, `letter-spacing` âm được hardcode theo hướng LTR.

Không có vấn đề **Blocker**; có 4 **High**, 8 **Medium**, 8 **Low/Note**. Điểm thẩm mỹ tổng: **6.5/10** — motion tĩnh rất trau chuốt, nhưng mọi trạng thái phản hồi (busy/success/error/loading) đều thiếu polish về mặt trực quan.

---

## Điểm mạnh

1. **Một easing dùng chung cho toàn site** — `--ease: cubic-bezier(.4,0,.2,1)` (`globals.css:1`) được tham chiếu nhất quán trong mọi transition của button, chip, icon-action, card, slot, nav-link, faq. Đây là dấu hiệu của một design-token có chủ đích, tạo cảm giác "một thương hiệu chuyển động".

2. **Hierarchy micro-interaction rõ ràng** — ba cấp nâng rời rạc: nút −1px (`globals.css:7`), timeline-card −2px (`globals.css:34`), featured-card −4px (`globals.css:16`); icon-action dùng scale 1.06 hover / 0.94 active như "vật lý" nhấn phím (`globals.css:7`). Cùng `transform .12s` cho phản hồi tức thì, `box-shadow .2s` cho "đổ bóng bay" chậm hơn một nhịp — kỹ thuật làm phong phú mà rất tiết chế.

3. **Focus-visible toàn cục rất tốt** — `:focus-visible{outline:3px solid var(--accent-2);outline-offset:2px}` (`globals.css:1`) có độ dày, offset và bo cong phù hợp, dễ thấy trên cả light/dark. Inputs trong planner dùng ring thay thế: `box-shadow:0 0 0 4px var(--lavender-soft)` (`globals.css:19,22`) — vẫn có indicator focus rõ.

4. **Sticky nav + backdrop blur được loang chống chói (glare) đúng chuẩn** — có `@supports(backdrop-filter)` để giảm độ trong suốt từ .86 → .82 khi blur khả dụng (`globals.css:4`), và dark mode có phiên bản riêng. Đây là chi tiết polish hiếm thấy ở site nhỏ.

5. **States được "kết nối" với aria đầy đủ** — `aria-live="polite"` trên messages/status (`PlanView.tsx:126`, `Planner.tsx:203,220`), `role="alert"` cho lỗi ở Planner/Explore/Settings, `aria-busy` trên history/settings/explore/roadtrip/login. Nền tảng SR tốt, chỉ thiếu ở mảng visual (mục High #1).

6. **Feedback tiến trình theo streaming** — Planner chuyển text qua các pha `sendingRequest → findingPlaces → routingPlan → working` (`Planner.tsx:99,130-131`) thay vì một "Đang tải…" đơ cứng. Đúng tinh thần của busy-state tốt (chỉ thiếu đồ họa).

7. **Một vài transition "nhỏ mà có hồn"**: dấu `+` của FAQ xoay 45° khi mở (`globals.css:16`), hover footer-link translateX(2px) (`globals.css:37`), `slot` nâng −1px kèm shadow (`globals.css:25`), `::selection` nhuộm lavender.

---

## Vấn đề theo mức

### 🔴 High

**H-1. PlanView đối xử mọi message như "thành công" — lỗi không có màu đỏ, không role=alert.**
`PlanView.tsx:122`:
```jsx
{message&&<div className="status" role="status">{t(message.key,message.values)}</div>}
{busy&&<div className="status" role="status">{t("busy")}</div>}
```
Trạng thái `message` mang các key **lỗi** (`actionFailed`, `refineFailed`, `versionsFailed`, `commentsFailed`, `regenerateFailed`, `offlineSaveFailed`, `copyFailed` — gán tại `PlanView.tsx:90,100,101,106,108-113`) nhưng **toàn bộ đều render `.status`** = màu accent (`globals.css:10`) chứ không phải `.error` = màu đỏ (`globals.css:10`), và dùng `role="status"` thay vì `role="alert"`. Kết quả: thất bại đổi điểm, lỗi bình luận, lỗi offline… trông y hệt "Đã sao chép liên kết" hay "Đã thay đúng một điểm". Ba trang khác làm đúng (`Planner.tsx:224-231`, `explore/page.tsx:65`, `settings/page.tsx:37`).
*Gợi ý:* tách `UiMessage` kèm cờ `error`, render `.error` + `role="alert"` khi lỗi; hoặc thống nhất helper `renderMessage`.

**H-2. Nút Danger ở dark mode không đọc được: `#ff9b8a` trên chữ trắng ≈ 2.0:1.**
Base: `.danger{background:var(--danger);color:#fff}` (`globals.css:7`). Dark mode chỉ đổi `--danger:#ff9b8a` (`globals.css:43`) và **không có override `.danger`** trong block dark — nền hồng nhạt + chữ trắng. Tính nhanh: #ff9b8a có luminance ≈ 0.465, contrast với #fff ≈ 2.04:1 — thấp hơn nhiều ngưỡng 4.5:1 (kể cả 3:1 cho UI text). Ảnh hưởng: nút "Xóa tài khoản", "Xóa dữ liệu" trong settings, nút xóa trong admin ở dark mode gần như không đọc được chữ.
*Gợi ý:* trong block dark thêm `.danger{background:var(--danger-soft);color:#ff9b8a}` (nền tối #3a1e18 + chữ sáng) hoặc đổi chữ sang `--ink` tối trên nền hồng.

**H-3. Contrast light mode không đạt AA cho text nhỏ: `--muted` và `--muted-2`.**
Từ `:root` (`globals.css:1`), tính trên `--paper:#f7f6f3` (L≈0.926):
- `--muted:#7f7482` → ≈ **4.1:1** (trên white 4.4:1). Body text 13–19px dùng muted rất phổ biến: `.lead` 19px, `.faq-body` 15px, `.trip-facts` 13px, `slot p` 13px, `disclaimer` 13px (`globals.css:10,16,25`). Dưới 4.5:1 → fail AA normal text.
- `--muted-2:#948b96` → ≈ **3.1:1** (white 3.3:1). Dùng cho các text nhỏ nhất: `.disclaimer` 13px (`globals.css:10`), `slot .source` 11px (`globals.css:25`), `last-updated` (`globals.css:25`), `admin`/`legal` small text.
- `--accent:#926cd6` (link, `.eyebrow` 12px, `.status`): ≈ **3.6–3.9:1** → fail AA cho link/caption.
Dark mode mảng này ổn (`--muted:#a99fae` trên nền tối ≈ 7.5:1).
*Gợi ý:* tối thiểu tăng `--muted-2` lên ~#6b6370 và `--accent` lên tông đậm hơn (~#7a5ab8) ở light; giữ token tách biệt `--link`/`--status` để không phá bản sắc.

**H-4. RTL chỉ "gắn" ở runtime, không có bất kỳ CSS nào theo `[dir=rtl]` → FOUC + layout sai hướng.**
`LocaleProvider.tsx:101` set `document.documentElement.dir` trong `useEffect` (client-only), còn `layout.tsx:9` hardcode `<html lang="vi">` (không dir). Hệ quả:
- Khi mở trang bằng locale ar/he (hoặc vừa đổi ngôn ngữ), **SSR/render đầu tiên chạy LTR**, sau đó effect chạy mới flip RTL → cả khối giao diện nhảy layout (FOUC) ở mỗi lần tải/đổi ngôn ngữ.
- Grep xác nhận **0 selector `[dir=rtl]`/`rtl:` trong `globals.css`**. Các hardcode hướng LTR sau sẽ sai khi RTL:
  - `text-align:left` trên `.login-card` (`globals.css:34`) — form login ép trái khi RTL phải phải.
  - `margin-right:12px` trên `.inline-check` (`globals.css:28`).
  - `margin-left:8px` trên `.nav-admin` (`globals.css:4`); `margin-left:auto` trên `.roadtrip-actions .primary` (`globals.css:31`).
  - `.footer-col a:hover{transform:translateX(2px)}` (`globals.css:37`) — link footer trượt **sang phải** trong ngữ cảnh RTL thay vì sang trái.
*Gợi ý:* đổi các hardcode sang logical properties (`margin-inline-end`, `margin-inline-start`, `text-align:start`, `translateX` → `transform:translateX(inline-start…)` hoặc dùng `[dir=rtl]` overrides); set `dir` sớm hơn (trong `<html dir=...>` khi SSR hoặc đầu `useLayoutEffect`, kèm hydrate-sync) để tránh nháy.

### 🟠 Medium

**M-1. Busy state chỉ là một dòng text — không spinner, không progress, không placeholder.**
`PlanView.tsx:122` busy = `<div className="status">{t("busy")}</div>` (vi: "Đang xử lý…"). Không có vòng quay, không overlay, không skeleton; danh sách itinerary không đổi → không rõ "đang chạy gì, khi nào xong". Nút disabled chỉ mờ opacity .5 (`globals.css:7`). `Planner.tsx:198-200` nút gửi là "↑" thuần, không đổi label trong lúc chạy (key `creatingPlan:"Đang lên lịch..."` tồn tại ở `LocaleProvider.tsx:75` nhưng **không dùng ở đâu**).
*Gợi ý:* spinner CSS nhỏ trong `.status`, hoặc dùng chính `typingPulse`/shimmer đã có (xem M-2).

**M-2. CSS animation "dead code": `typingPulse` và `shimmer` chưa bao giờ được render.**
- `.bubble.typing` + `@keyframes typingPulse` (`globals.css:22`) — không component nào render `<div class="bubble typing">`; PlanView chỉ render `bubble assistant|user` (`PlanView.tsx:126`), Planner chỉ render `bubble assistant` welcome. Typing indicator được thiết kế nhưng không bao giờ hiện — chat-refine lâu (30s timeout) không có "con bot đang gõ".
- `.slot-photo.loading::after` + `@keyframes shimmer` (`globals.css:25`) — `slotPhoto()` render `<div className="slot-photo">` không bao giờ kèm `.loading` (`PlanView.tsx:117`); ảnh dùng `next/image` không có `onLoadingComplete` để bật class → shimmer chết.
*Gợi ý:* render typing-bubble khi `busy==="refine"`, và bật `.loading` cho slot-photo đến khi `onLoadingComplete` — tận dụng CSS đã có, gần như miễn phí.

**M-3. Không có skeleton ở bất kỳ đâu — mọi loading là text tĩnh.**
- Map: `MapLoading` = `<div className="card map">{t("mapLoading")}</div>` (`PlanView.tsx:13`) — một ô trắng trơn với chữ.
- History: "Đang tải…" (`history/page.tsx:53-55`), không skeleton cho timeline.
- Explore/Roadtrip: khi search/build, `result` bị `setResult(null)` → phần kết quả **biến mất hoàn toàn** rồi bung ra đột ngột (`explore/page.tsx:52-53`, `roadtrip/page.tsx:52`), gây nhảy layout.
*Gợi ý:* skeleton giả chiều cao cho offer-grid/timeline/map (đã có shimmer, chỉ cần bọc).

**M-4. Status message không auto-dismiss, không phân biệt loại, gây layout-shift.**
`PlanView` message tồn tại vô thời hạn đến khi action kế tiếp (start() xóa message, `PlanView.tsx:87`); `copied`/`swipeSuccess`/`commentAdded` treo mãi trên màn hình. Message xuất hiện/ẩn làm đẩy cả khối workspace xuống/dâng lên (`margin-top:14px`, `globals.css:10`) — không có vùng dành sẵn. Không hệ thống toast, không tự ẩn, không fade.
*Gợi ý:* toast góc với auto-dismiss 3–5s + enter/exit transition; hoặc ít nhất dành sẵn một dòng status cố định.

**M-5. Day-tabs thiếu semantics & phản hồi chuyển đổi: không `role="tablist/tab"`, không `aria-selected`, không cập nhật chỉ số focus.**
`PlanView.tsx:127` button tab chỉ có `className={index===activeDay?"active":""}`. So với Explore dùng `role="tablist"` + `aria-selected` (`explore/page.tsx:60`) thì đây là lỗi nhất quán. Khi đổi ngày, `slots` thay đổi đột ngột (không transition), focus không được quản lý (người dùng bàn phím "mất" vị trí).
*Gợi ý:* thêm aria-selected + keyboard arrow-nav, và transition nhẹ (fade/slide 150ms) khi đổi day.

**M-6. Dark mode không override màu địa lý/bản đồ: marker, polyline, popup cứng màu LTR-light.**
`MapView.tsx:37,49` hardcode `#e4572e`/`#0f766e`; popup và attribution không theo theme (`globals.css:40` chỉ bo góc). Trong dark mode, khu vực bản đồ sáng chói lọt giữa UI tối. Ngoài ra popup dựng HTML chuỗi nối (`MapView.tsx:42`) — mảng này thuộc agent khác nhưng về visual: ảnh popup không có kích thước/placeholder (nên `map-popup img` CSS `globals.css:25` là đúng, chỉ thiếu kích thước khung khi ảnh lỗi).
*Gợi ý:* cho markers đọc từ CSS vars, hoặc thêm lớp `.dark` để nhúng CSS của Leaflet; tối thiểu đặt container `.map` có nền tối ở dark.

**M-7. RTL typography: `letter-spacing` âm trên heading phá chữ Ả Rập/Hebrew.**
`h1,h2,h3{letter-spacing:-.02em}` (`globals.css:1`), `letter-spacing:-.035em` trên hero (`globals.css:13,28,31`). Với chữ Ả Rập (ar) dùng nối glyph, letter-spacing âm gây dính/rách liên kết chữ; Hebrew cũng nhạy. Không có nhánh `[dir=rtl]` để reset.
*Gợi ý:* `[dir=rtl] h1,[dir=rtl] h2,[dir=rtl] h3{letter-spacing:0}` hoặc dùng `letter-spacing:.01em` cho RTL.

**M-8. Tương tác không đồng bộ khi busy: itinerary & map vẫn "sống" trong lúc chạy thao tác.**
Khi `busy`, các nút actions/chat/swap bị disabled (`PlanView.tsx:114,127`), nhưng `.slot-select` (phủ toàn card, `PlanView.tsx:127`) và marker bản đồ (`onSelect`, `MapView.tsx:39`) **vẫn nhận click** → người dùng chọn điểm trong lúc refine đang chạy, xong kết quả set `selectedId` lại theo plan mới (`PlanView.tsx:106`) — lệch giữa kỳ vọng và kết quả.
*Gợi ý:* `disabled` cho `.slot-select`/map interactions khi busy, hoặc giữ selectedId của user.

### 🟡 Low

**L-1. Inputs override focus ring bằng `:focus` (thay vì `:focus-visible`)** (`globals.css:19,22`) — chuột click cũng hiện ring, không gây hại nhưng mất "chỉ bàn phím mới hiện"; ring `4px lavender-soft` trong dark (`--lavender-soft:#352438` trên `--surface-2:#2a182e`, `globals.css:43`) quá tối, khó thấy.

**L-2. `scroll-behavior:smooth` (`globals.css:1`) không nằm trong `prefers-reduced-motion:reduce`** — `html` vẫn smooth-scroll cho người yêu cầu giảm chuyển động; chính block reduce chỉ tắt transition/animation, không tắt smooth scroll.

**L-3. `prefers-reduced-motion` dùng override toàn cục `.01ms !important`** (`globals.css:1`) — hiệu quả nhưng vẫn cho animation infinite chạy 1 iteration; ổn, chỉ nên thêm `scroll-behavior:auto`.

**L-4. aria-label hardcode ngôn ngữ:** `Navigation.tsx:29` `aria-label="Main"` (tiếng Anh cố định), `MapView.tsx:58` `aria-label="Bản đồ lịch trình"` (tiếng Việt cố định) — không theo locale.

**L-5. Footer/legal hardcode nội dung:** `Footer.tsx:26` "Support", `:30` "Điều khoản", `:31` "Bảo mật" không dịch; `layout.tsx:8` metadata tiếng Việt cố định.

**L-6. Unused translation keys phản ánh tính năng thiếu:** `creatingPlan` (`LocaleProvider.tsx:75`), `undoSuccess` (`i18n-core.ts:9`) không được dùng — gợi ý nút Undo sau restore/refine chưa có.

**L-7. Opacity disabled không nhất quán:** `.5` cho button/chip/icon-action (`globals.css:7`) nhưng `.55` cho `.planner .chat-box button` (`globals.css:19`) — lệch nhẹ, không đáng kể.

**L-8. Nút Danger light mode ở biên:** chữ trắng trên `#bb4d45` ≈ 4.9:1, hover `#a03a33` ≈ 5.8:1 — pass nhưng sát ngưỡng; cân nhắc tối hóa `--danger`.

### ⚪ Note

- **Bubbles RTL:** `.bubble.assistant{align-self:flex-start}` (`globals.css:22`) trong RTL tự chuyển sang phải (start = right) — hợp lệ về kỹ thuật, nhưng quy ước nhiều app chat RTL vẫn để bot bên trái; không coi là lỗi, chỉ note.
- **Radius bubble không mirror:** `border-bottom-left-radius:6px`/`border-bottom-right-radius:6px` (`globals.css:22`) không đổi theo RTL — cosmetic, khó nhận ra.
- **Scrollbar:** `day-tabs{scrollbar-width:thin}` (`globals.css:25`); `.messages`, `.itinerary-panel` dùng scrollbar mặc định, không có fade-mask ở mép — thiếu polish nhưng không lỗi.
- **Layout-shift do message** (`H-1`/`M-4`) làm hero/planner nhảy vài px khi status xuất hiện.

---

## Checklist

### Motion
- [x] Easing duy nhất (`--ease`) dùng nhất quán
- [x] Duration hợp lý: transform .12s, shadow/color .2s
- [x] Hover lift đa cấp (−1/−2/−4px) + icon scale + active .94
- [x] FAQ +, footer link, slot hover, selection đều có transition
- [x] `prefers-reduced-motion:reduce` toàn cục
- [ ] **Typing indicator đã viết nhưng không hiển thị** (dead code)
- [ ] **Shimmer đã viết nhưng không hiển thị** (dead code)
- [ ] **Không có transition khi đổi day-tab / xuất hiện result** (bung đột ngột)
- [ ] **Không có entrance/reveal animation cho landing** (page tĩnh — tùy chọn)
- [ ] **Reduced-motion không tắt `scroll-behavior:smooth`**

### States (loading / empty / error / success)
- [x] Planner streaming nhiều pha text
- [x] Empty state history ("Chưa có chuyến đi nào.")
- [x] Error + retry đầy đủ ở Planner (`retry-panel`, "Thử lại")
- [x] `aria-busy` đúng chỗ (history/settings/explore/roadtrip/login)
- [ ] **Busy chỉ text, không spinner/progress** (PlanView:122)
- [ ] **Error trong PlanView render như success** (H-1)
- [ ] **Không skeleton map/itinerary/offers** (MapLoading chỉ text)
- [ ] **Message không auto-dismiss, không phân loại visual**
- [ ] **Result bị xoá hẳn khi search lại → nhảy layout**

### Accessibility (visual)
- [x] `:focus-visible` 3px accent-2 toàn cục
- [x] Contrast body/ink, brand/contrast, footer tốt (≥7:1)
- [x] aria-live/role=status/alert dùng hợp lý ở đa số trang
- [x] Icon buttons đều có aria-label (↑, ↻, ×, slot-select)
- [ ] **Dark `.danger` 2.0:1 — fail**
- [ ] **Light `--muted`/`--muted-2`/`--accent` < 4.5:1 cho text nhỏ**
- [ ] **Day-tabs thiếu role/aria-selected** (lệch với inventory-tabs)
- [ ] **`aria-label` hardcode tiếng Anh/Việt** (Navigation/MapView)

### RTL (ar/he)
- [x] `document.documentElement.dir` được set cho ar/he (LocaleProvider:101)
- [x] Flex/grid tự mirror (bubbles, stop-input, chat-box grid)
- [ ] **Không selector `[dir=rtl]` nào trong CSS**
- [ ] **SSR FOUC: dir set ở useEffect, html lang="vi" hardcode** (H-4)
- [ ] **`text-align:left` trên login-card**
- [ ] **margin-left/right hardcode** (nav-admin, inline-check, primary)
- [ ] **footer hover translateX(2px) sai hướng**
- [ ] **letter-spacing âm trên heading Ả Rập/Hebrew**

### Scroll & sticky
- [x] Nav sticky + blur + @supports + dark variant
- [x] `scroll-behavior:smooth`
- [x] day-tabs `overflow:auto` + thin scrollbar
- [ ] Không scroll-margin cho focus khi cuộn dưới nav sticky
- [ ] Không fade-mask/scrollbar tùy chỉnh cho messages/itinerary-panel

---

## Kết luận

**Điểm thẩm mỹ: 6.5/10** — nền tảng motion và focus-visual rất trau chuốt, nhưng toàn bộ tầng phản hồi động (busy/success/error/loading/skeleton) và RTL đang ở trạng thái "cài đặt nửa vời": mọi trạng thái chỉ là chữ, lỗi bị nhuộm màu thành công ở màn hình quan trọng nhất (PlanView), và mỗi nét RTL bị hardcode theo hướng trái.

---

**Confidence: 8/10**

**Ground-truth tally:** 21/25 kết luận chính dựa trực tiếp trên code (file:line): H-1 (PlanView.tsx:122 + globals.css:10), H-2 (globals.css:7,43), H-3 (globals.css:1,10,25 + tính contrast), H-4 (LocaleProvider.tsx:101, layout.tsx:9, grep rtl=0, globals.css:28,31,34,37), M-1 (PlanView.tsx:122, LocaleProvider.tsx:75), M-2 (globals.css:22,25, PlanView.tsx:117,126), M-3 (PlanView.tsx:13, history:53, explore:52, roadtrip:52), M-4 (PlanView.tsx:87, globals.css:10), M-5 (PlanView.tsx:127, explore:60), M-6 (MapView.tsx:37,42,49), M-7 (globals.css:1,13), M-8 (PlanView.tsx:114,127, MapView.tsx:39), L-1 (globals.css:19,22), L-2/L-3 (globals.css:1), L-4 (Navigation.tsx:29, MapView.tsx:58), L-5 (Footer.tsx:26-31), L-6 (i18n-core.ts:9), L-8 (globals.css:7), plus các điểm mạnh (globals.css:1,4,7,16,34,37). 4/25 còn lại là phán đoán chuyên môn không kiểm chứng được bằng code: mức độ cảm nhận FOUC RTL ngoài runtime (H-4), mức ảnh hưởng letter-spacing lên render chữ Ả Rập (M-7), mức nhận diện bubble RTL (Note 1), và đánh giá aesthetic tổng (6.5/10).
