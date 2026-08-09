# Fixes Applied (Phase 5) — Beauty deep-dive round 2

Áp dụng 5 fix Tier 0 từ `research/ui-aesthetics-beauty/08-executive-briefing.md`, sau khi được user duyệt ("có"). Mỗi fix được **verify trong browser thật** (Edge headless 151 CDP) sau khi sửa.

Ngày: 2026-08-09. Chỉ sửa frontend. Không thay đổi logic nghiệp vụ.

## Tier 0 — 5 fix đã áp dụng

| # | Vấn đề | File | Thay đổi | Verify (render thật) |
|---|---|---|---|---|
| T0-1 | Font Inter/Fig Grotesk **chưa bao giờ tải** (toàn UI = Segoe UI) | `frontend/app/layout.tsx` | Thêm `import { Inter } from "next/font/google"`; `const inter = Inter({ subsets:["latin","vietnamese"], variable:"--font" })`; gắn `className={inter.variable}` lên `<body>` | `document.fonts` = 4 faces Inter loaded; `body.fontFamily` = `__Inter_…, __Inter_Fallback_…`; build tạo 7 file `.woff2` self-host |
| T0-2 | Trang plan **tràn ngang ~8px** (scrollbar xuất hiện, map cắt mép) do `width:100vw` full-bleed | `frontend/app/globals.css:25` (`.workspace-page`) | Bỏ `width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)` → còn `max-width:1500px;margin:0 auto;padding:0 20px` | `scrollWidth==clientWidth` (1399==1399), `hasHScroll=false`, workspace căn giữa (left=124, right=1276). **Ghi chú:** đã test 4 cách trong browser — chỉ cách này thực sự hết lỗi |
| T0-3 | Map dùng màu brand **cũ** teal `#0f766e`/orange `#e4572e` lạc palette | `frontend/components/MapView.tsx:37,49`; `frontend/components/RoadTripMap.tsx:15-16` | Route + marker thường → `#7d4fb8` (accent); marker selected/start → `#bb4d45` (danger) | 8 path render đúng 2 màu `#7d4fb8` + `#bb4d45` |
| T0-4 | Dark mode `::selection` **vô hình** (lavender on lavender) | `frontend/app/globals.css:43` (khối dark) | Thêm `::selection{background:var(--lavender);color:var(--brand-contrast)}` | dark: bg `rgb(205,179,255)` + fg `rgb(42,24,46)` — nhìn thấy rõ |
| T0-5 | Dark mode `.cta-banner` là **khối sáng vỡ** (gradient lavender + chữ trắng ~1.35:1) | `frontend/app/globals.css:43` (khối dark) | Override: gradient tối `var(--surface-2)→var(--lavender-soft)→var(--line-2)`, chữ `var(--ink)`/`var(--muted)`, nút `.primary` = brand/brand-contrast | dark: bg gradient `#2a182e→#352438→#3d2b42`, chữ `#eae8ea`, nút `#cdb3ff`/`#2a182e` — tương phản tốt |

## Kiểm chứng

- `npx tsc --noEmit` → pass
- `npm run lint` → pass (No ESLint warnings or errors)
- `npm run build` → pass (14 routes), Inter self-host 7 woff2
- `node --test tests/i18n.test.mjs` → pass
- Render thật qua CDP: cả 5 fix đo được đúng kết quả mong đợi (bảng trên)
- Backend không đổi (111 passed, 5 skipped trước đó)

## Các fix Tier 1+ chưa làm (đợi user yêu cầu)

- T1: tăng `--shadow-sm`/tối `--line` để light mode hết trống 95%
- T1: thêm class `.card` cho admin booking queue (`admin/page.tsx:569`)
- T1: dọn h1 clamp chết (`main:not(.hero)>h1` 62px sitewide)
- T1: `font:inherit` → `font-family:inherit;font-size:inherit;line-height:inherit`; đặt font-size tường minh cho body/h1/small
- T1: History empty state + button size scale + bỏ `width:100%` khỏi `.primary` base

---

# Fixes Tier 1 (Phase 6) — Beauty deep-dive round 2

Áp dụng 8 fix Tier 1 theo `08-executive-briefing.md` sau khi user duyệt ("có"). Verify trong browser thật (Edge 151 CDP) sau khi sửa.

Ngày: 2026-08-09. Chỉ sửa frontend. Không thay đổi logic nghiệp vụ.

## Tier 1 — 8 fix đã áp dụng

| # | Vấn đề | File | Thay đổi | Verify (render thật) |
|---|---|---|---|---|
| T1-6 | Light mode card **mất viền** trên nền trống 95% | `globals.css:1` | `--line:#eae8ea → #e0dde0`; `--shadow-sm:0 1px 2px rgba(42,24,46,.05) → 0 2px 6px rgba(42,24,46,.08)` | light: `--shadow-sm`=`0 2px 6px rgba(42,24,46,.08)`, `--line`=`#e0dde0`, `.card` shadow hiện rõ |
| T1-7 | Admin booking queue hiện **text trần** (thiếu `.card`) | `admin/page.tsx:569` | `<article className="offer-card">` → `"offer-card card"` | bundle chứa `className:"offer-card card"` |
| T1-8 | 5 h1 clamp chết do `main:not(.hero)>h1` (0,1,2) đè | `globals.css:10` | Xóa `main:not(.hero)>h1`; base h1 = `clamp(30px,4vw,44px)` trong rule h1/h2/h3 | explore h1=42px, admin h1=40px, roadtrip h1=42px, history h1=30px (thay vì 62px sitewide) |
| T1-9 | `font:inherit` làm form control mất line-height | `globals.css:1` | → `font-family:inherit;font-size:inherit;line-height:inherit;color:inherit` | input line-height=24.8px, font=`__Inter_…` (không còn Arial/normal) |
| T1-10 | body/h1/h3/small không có font-size tường minh | `globals.css:1` | `body{font-size:16px}`; `h1{clamp(30px,4vw,44px)} h2{clamp(24px,3vw,32px)} h3{20px}`; `small{13px}` | body=16px, small=13px (thay vì 13.33px UA) |
| T1-11 | History **empty state chỉ là dòng chữ xám** + footer chiếm 37% màn hình | `history/page.tsx:55`, `globals.css` | Thêm `.empty-state` (illustration + CTA `createPlan`); `.site-footer` `margin-top:72px→48px`, padding `56px→48px` | `.empty-state` xuất hiện khi rỗng, CTA pill; footer margin-top=48px |
| T1-12 | Không có **scale kích thước nút** (53/46/49/43/38px) + rule chết | `globals.css:7,25,28` | Thêm token `--btn-h:52px;--btn-h-sm:44px`; base nút `min-height:var(--btn-h)`; `.inventory-search .primary` → `min-height:var(--btn-h-sm)`; xóa `.trip-actions .icon-action` (dead); `.retry-action` → `min-height:var(--btn-h-sm)` | `.cta-banner .primary` min-height=52px; `.inventory-search .primary`=44px; nút nhất quán |
| T1-13 | `.primary{width:100%}` là **bom chờ nổ** (mọi nơi phải opt-out) | `globals.css:7`; `login/page.tsx:72` | Bỏ `width:100%` khỏi `.primary` base; thêm utility `.form-submit{width:100%}`; áp cho nút full-width duy nhất là login mock-google | `.primary` mặc định = inline-flex content-width (CTA hero thành pill 183px); `.primary.form-submit` = full-width 739px |

## Kiểm chứng

- `npx tsc --noEmit` → pass
- `npm run lint` → pass (No ESLint warnings or errors)
- `npm run build` → pass (13 static + plan dynamic)
- `node --test tests/i18n.test.mjs` → 18/18 pass
- Render thật qua CDP (1440px, light+dark): tokens light mode, h1 per-page, empty state, button min-height đều đúng
- Backend không đổi

## Các fix Tier 2+ chưa làm (đợi user yêu cầu)

- Card admin `admin-support` section còn nhiều nội dung thô
- Cân nhắc `.empty-state` thêm min-height khi footer vẫn chiếm tỉ trọng trên trang ngắn
- Dark mode `--line` cũng có thể tăng contrast thêm nếu cần
