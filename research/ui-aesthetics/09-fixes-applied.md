# Fixes Applied — Đánh giá thẩm mỹ giao diện

File ghi lại các sửa đổi code đã được áp dụng (Phase 5) sau deep-dive thẩm mỹ, theo từng phát hiện trong `06-synthesis.md` / `07-red-team.md`.

Ngày: 2026-08-08. Chỉ sửa frontend. Không có thay đổi logic nghiệp vụ.

## Tier 0 (phải sửa trước khi công khai)

| # | Vấn đề | File | Thay đổi |
|---|---|---|---|
| T0-1 | Contrast dark-mode `.danger` ≈2:1 (chữ trắng trên `#ff9b8a`) | `frontend/app/globals.css` (khối dark) | Thêm `.danger{color:var(--brand-contrast)}` + `.danger:hover{background:var(--danger-soft);color:var(--danger)}` |
| T0-2 | Contrast dark-mode `.chat-box button` ≈1.83:1 | `frontend/app/globals.css` (khối dark) | Thêm `.chat-box button{color:var(--brand-contrast)}` + hover |
| T0-3 | `<main>` lồng nhau (layout + mọi trang) vô hiệu `max-width:1500px` của workspace | `frontend/app/layout.tsx` | Đổi `<main className="shell">` → `<div className="shell">` |
| T0-4 | Panel chat bị nén ~276px trong workspace | `frontend/app/globals.css` | Cân lại grid: `minmax(240px,.6fr) minmax(360px,1.2fr) minmax(340px,1.05fr)` + full-bleed `width:100vw;margin-left:calc(50% - 50vw)` để workspace 1500px có hiệu lực |

## Tier 1 (nên sửa trước khi mở rộng)

| # | Vấn đề | File | Thay đổi |
|---|---|---|---|
| T1-1 | Accent light 3.64:1 (link khó đọc) | `globals.css:1` | `--accent:#926cd6` → `#7d4fb8` (5.28:1); giữ nguyên `--accent-2:#ae86f7` |
| T1-2 | `--muted` light 4.11:1 | `globals.css:1` | `--muted:#7f7482` → `#6f6570` (5.15:1) |
| T1-3 | `.icon-action:hover` dark 1:1 (nút biến mất khi hover) | `globals.css` (khối dark) | `color:var(--ink-3)` → `color:var(--brand-contrast)` |
| T1-4 | Admin lưới 5 thẻ / 4 cột vỡ | `globals.css` | `.admin-strip` → `repeat(auto-fit,minmax(170px,1fr))` |
| T1-5 | Tiếng Việt không dấu hard-code (toàn trang Admin) | `frontend/app/admin/page.tsx` | Sửa ~45 chuỗi: status labels, error messages, tiêu đề, nút, label, placeholder, empty states sang tiếng Việt có dấu |
| T1-6 | Nút "Huy" không dấu còn sót | `frontend/app/admin/page.tsx:580` | → "Hủy" |

## Tier 2 (polish)

| # | Vấn đề | File | Thay đổi |
|---|---|---|---|
| T2-1 | Hero h1 floor 48px quá to trên mobile | `globals.css` | Thêm `@media(max-width:600px){.hero h1{font-size:clamp(34px,9vw,48px)}}` |
| T2-2 | Message không auto-dismiss | `frontend/components/PlanView.tsx` | Thêm effect ẩn message sau 5s |
| T2-3 | Busy state chỉ là text | `PlanView.tsx` + `globals.css` | Thêm spinner (vòng quay CSS) + layout flex |
| T2-4 | 3 kiểu focus input khác nhau | `globals.css:1` | Thêm rule toàn cục `input:focus,select:focus,textarea:focus` dùng chung pattern box-shadow lavender |

## Không áp dụng (structural / cần quyết định sản phẩm)

- **Spacing scale toàn hệ thống** — đòi hỏi dò lại mọi giá trị; rủi ro phá layout cao.
- **Drawer → overlay thật** (version/comment/feedback) — thay đổi cấu trúc tương tác.
- **RTL cho ar/he** — 19 ngôn ngữ nhưng chưa có `[dir=rtl]`; cần hỗ trợ hệ thống, không phải fix 1 file.
- **Font Inter không được tải** — chỉ khai báo `--font`; tự-host Inter là việc build/deploy.
- **Icon Unicode ↑↻→** — thay bằng SVG cần thư viện icon; hiện hiển thị được trên đa số OS.
- **Typo "· local" login** — là logic hiển thị local env, không phải lỗi.
- **Typo `© OpenStreetMap`** — xác minh: cả 2 file map **đã đúng** `©` (U+00A9), lỗi do hiển thị console trước đó.

## Kiểm chứng

- `npx tsc --noEmit` → pass
- `npm run lint` → pass
- `node --test tests/i18n.test.mjs` → 18 pass
- `npm run build` → pass (14 routes)
- Contrast đều tính bằng công thức WCAG từ hex trong code trước khi đổi giá trị
