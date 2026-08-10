---
title: 'Chuyá»ƒn toÃ n bá»™ giao diá»‡n tá»« tÃ­m sang xanh'
type: 'refactor'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '0fcf0ce'
context: []
---

<frozen-after-approval reason="human-owned intent â€” do not modify unless human renegotiates">

## Intent

**Problem:** Giao diá»‡n hiá»‡n dÃ¹ng há»‡ tÃ­m lavender/plum á»Ÿ token ná»n táº£ng, component, báº£n Ä‘á»“ vÃ  dark mode, khÃ´ng cÃ²n phÃ¹ há»£p Ä‘á»‹nh hÆ°á»›ng mÃ u xanh trong máº«u Ä‘Ã£ duyá»‡t.

**Approach:** Chuyá»ƒn semantic color system sang xanh HÃ  Ná»™i báº±ng cÃ¡ch thay giÃ¡ trá»‹ token toÃ n cá»¥c vÃ  cÃ¡c mÃ u tÃ­m hard-code; giá»¯ nguyÃªn tÃªn token Ä‘á»ƒ giá»›i háº¡n blast radius, rá»“i báº£o vá»‡ palette má»›i báº±ng kiá»ƒm thá»­ source contract vÃ  kiá»ƒm tra tÆ°Æ¡ng pháº£n.

## Boundaries & Constraints

**Always:** Ãp dá»¥ng xanh cho logo gradient, navigation, tiÃªu Ä‘á»/eyebrow, focus, button, chip, chat bubble, timeline, badge, tráº¡ng thÃ¡i, map marker/route, footer vÃ  dark mode. Báº£ng sÃ¡ng dÃ¹ng xanh Ä‘áº­m `#086B27`, hover `#075A22`, xanh trung `#5FA858`, xanh nháº¡t `#E3EFE0`, ná»n xanh ráº¥t nháº¡t `#F3FAF1`, footer `#063B1B`. Giá»¯ danger Ä‘á», warning vÃ ng, info xanh lam vÃ  ná»n trung tÃ­nh khi chÃºng mang Ã½ nghÄ©a tráº¡ng thÃ¡i riÃªng. TÆ°Æ¡ng pháº£n chá»¯/control pháº£i Ä‘á»c Ä‘Æ°á»£c á»Ÿ light/dark mode.

**Ask First:** Äá»•i bá»‘ cá»¥c, typography, ná»™i dung, icon, áº£nh hoáº·c hÃ nh vi; Ä‘á»•i mÃ u semantic danger/warning/info; thay nháº­n diá»‡n thÆ°Æ¡ng hiá»‡u ngoÃ i palette.

**Never:** KhÃ´ng sá»­a backend/thuáº­t toÃ¡n/API; khÃ´ng thay tÃªn class hay cáº¥u trÃºc component náº¿u khÃ´ng cáº§n; khÃ´ng Ä‘á»ƒ láº¡i mÃ£ tÃ­m cÅ© trong UI Ä‘ang render; khÃ´ng lÃ m máº¥t focus-visible hoáº·c selected state.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Light mode | Má»i trang frontend | Accent, surface tint, footer vÃ  map dÃ¹ng há»‡ xanh nháº¥t quÃ¡n | Semantic danger/warning/info giá»¯ nguyÃªn |
| Dark mode | `prefers-color-scheme: dark` | Xanh sÃ¡ng/dark-green surface cÃ³ tÆ°Æ¡ng pháº£n tÆ°Æ¡ng Ä‘Æ°Æ¡ng theme cÅ© | KhÃ´ng dÃ¹ng mÃ u chá»¯ xanh Ä‘áº­m trÃªn ná»n tá»‘i |
| Interactive state | Hover, focus, active, selected, disabled | Tráº¡ng thÃ¡i phÃ¢n biá»‡t rÃµ báº±ng xanh vÃ  focus ring | Disabled váº«n nháº­n biáº¿t Ä‘Æ°á»£c |
| Map | Plan map vÃ  road-trip map | Marker/route tÃ­m Ä‘á»•i sang xanh, selected danger giá»¯ nguyÃªn | KhÃ´ng Ä‘á»•i tá»a Ä‘á»™/logic chá»n |

</frozen-after-approval>

## Code Map

- `frontend/app/globals.css` â€” token light/dark vÃ  toÃ n bá»™ component styling dá»±a trÃªn palette.
- `frontend/components/MapView.tsx` â€” marker/route cá»§a báº£n Ä‘á»“ lá»‹ch trÃ¬nh.
- `frontend/components/RoadTripMap.tsx` â€” marker/route cá»§a báº£n Ä‘á»“ road trip.
- `frontend/tests/i18n.test.mjs` â€” contract ngÄƒn mÃ u tÃ­m cÅ© quay láº¡i vÃ  khÃ³a palette xanh.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/app/globals.css` â€” thay palette token light/dark vÃ  hard-code purple báº±ng xanh semantic.
- [x] `frontend/components/MapView.tsx`, `frontend/components/RoadTripMap.tsx` â€” thay mÃ u marker/route tÃ­m, giá»¯ selected/error Ä‘á».
- [x] `frontend/tests/i18n.test.mjs` â€” assert palette xanh vÃ  khÃ´ng cÃ²n hex tÃ­m cÅ© trong source frontend Ä‘Æ°á»£c kiá»ƒm soÃ¡t.

**Acceptance Criteria:**
- Given báº¥t ká»³ mÃ n hÃ¬nh frontend, when render light hoáº·c dark mode, then khÃ´ng cÃ²n thÃ nh pháº§n nháº­n diá»‡n tÃ­m vÃ  hierarchy/behavior khÃ´ng Ä‘á»•i.
- Given báº£n Ä‘á»“ cÃ³ route vÃ  marker, when render/select, then mÃ u máº·c Ä‘á»‹nh lÃ  xanh vÃ  selected marker váº«n ná»•i báº­t.
- Given keyboard navigation, when focus component, then focus ring xanh cÃ³ Ä‘á»™ tÆ°Æ¡ng pháº£n rÃµ.

## Spec Change Log

- 2026-08-10: Applied the approved Hanoi green palette to light/dark tokens and maps; added regression coverage for required green values and retired purple hex values.
- 2026-08-10: Review corrected primary/hover semantic mapping and strengthened focus/small-text contrast; tests now bind required roles, dark tokens and preserved semantic colors. KEEP the green map conversion and unchanged layout/behavior.

## Design Notes

Giá»¯ cÃ¡c tÃªn biáº¿n `--lavender*` Ä‘á»ƒ trÃ¡nh rewrite rá»™ng vÃ  regression; giÃ¡ trá»‹ cá»§a chÃºng trá»Ÿ thÃ nh ba cáº¥p green tint. Semantic naming cÃ³ thá»ƒ refactor riÃªng sau. Shadow RGB Ä‘á»•i tá»« plum sang green-black nháº¹ Ä‘á»ƒ loáº¡i bá» sáº¯c tÃ­m.

## Suggested Review Order

**Theme foundation**

- Token light/dark chuyển toàn bộ component sang hệ xanh semantic.
  [`globals.css:1`](frontend/app/globals.css#L1)

- Override ánh xạ đúng primary, hover, focus và muted contrast.
  [`globals.css:73`](frontend/app/globals.css#L73)

**Map identity**

- Route và marker lịch trình dùng xanh, selected vẫn giữ danger đỏ.
  [`MapView.tsx:37`](frontend/components/MapView.tsx#L37)

- Road-trip map áp dụng cùng quy tắc màu mà không đổi logic.
  [`RoadTripMap.tsx:14`](frontend/components/RoadTripMap.tsx#L14)

**Regression protection**

- Contract khóa semantic roles, dark palette và loại mã tím cũ.
  [`i18n.test.mjs:28`](frontend/tests/i18n.test.mjs#L28)

## Verification

**Commands:**
- `npm test` trong `frontend` â€” toÃ n bá»™ contract pass.
- `npx tsc --noEmit` trong `frontend` â€” typecheck sáº¡ch.
- `rg` palette tÃ­m cÅ© trong `frontend` â€” khÃ´ng cÃ²n mÃ£ tÃ­m render-time.
- `git diff --check` â€” diff sáº¡ch.
