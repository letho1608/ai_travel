---
title: 'Thiết kế thẻ tóm tắt lịch trình theo ảnh mẫu'
type: 'feature'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '2230c48017fc9d12afe0b6b3547becbc6efc2e36'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Trang kế hoạch hiện ưu tiên workspace ba cột và nhóm nhiều công cụ, nên người dùng chưa có một thẻ tóm tắt lịch trình trực quan giống ảnh mẫu với ảnh đại diện, chi phí/thời lượng/thời tiết, các điểm dừng chính và ba hành động nổi bật.

**Approach:** Thêm thẻ tổng quan responsive ở đầu trang kế hoạch, lấy hoàn toàn từ `Plan` hiện có. Thẻ có ảnh đại diện an toàn, tóm tắt các điểm dừng của ngày đang chọn, nút “Lưu kế hoạch”, “Chia sẻ”, và nút “Tạo lại” bên dưới; workspace chi tiết, bản đồ, chat và các công cụ hiện hành tiếp tục tồn tại phía dưới.

## Boundaries & Constraints

**Always:** Tái sử dụng logic share và regenerate hiện có; “Lưu kế hoạch” ghi snapshot hiện tại vào localStorage bằng cơ chế offline sẵn có và đưa phản hồi rõ ràng. Dùng ảnh điểm dừng đầu tiên nếu hợp lệ, có fallback không vỡ layout; nội dung và nút phải responsive, hỗ trợ keyboard/screen reader, và không che khuất trạng thái busy/error.

**Ask First:** Mọi thay đổi API/backend, thay đổi ý nghĩa regenerate, xóa workspace chi tiết, hoặc biến “Lưu kế hoạch” thành lưu tài khoản/cloud.

**Never:** Hard-code lịch trình/ảnh/chi phí từ ảnh mẫu; tạo plan mới khi người dùng bấm Save hoặc Share; gọi regenerate hai lần; bỏ các công cụ download, calendar, comment, version, feedback hiện có; làm ảnh remote không hợp lệ khiến trang crash.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Plan đầy đủ | Có ảnh, constraints và slots | Thẻ hiện ảnh, title, facts, tối đa các điểm dừng ngày active và ba hành động | N/A |
| Không có ảnh | Slot đầu không có ảnh hoặc ảnh lỗi | Hiển thị nền fallback có chủ đích | Không để khoảng trống/broken image |
| Không có slot | Ngày active rỗng | Thẻ vẫn hiện title/facts/actions; phần điểm dừng báo trạng thái phù hợp | Không truy cập phần tử undefined |
| Lưu thành công | localStorage khả dụng | Ghi snapshot plan/version và hiện xác nhận “Đã lưu kế hoạch” | Không gọi API |
| Lưu thất bại | localStorage quota/permission lỗi | Giữ nguyên plan và hiện lỗi offline hiện có | Không báo thành công giả |
| Chia sẻ | Native share hỗ trợ hoặc không hỗ trợ | Mở share sheet hoặc copy public link như hiện tại | Giữ feedback hiện có |
| Tạo lại | Người dùng bấm khi idle | Gọi đúng regenerate hiện tại, khóa nút trong khi chờ và cập nhật thẻ khi thành công | Plan cũ được giữ nếu request lỗi |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — state plan, slots active, ảnh, share, offline persistence, regenerate và toàn bộ render kế hoạch.
- `frontend/app/globals.css` — layout workspace và các primitives card/button; cần namespace cho summary card.
- `frontend/lib/workspace-translations.ts` — nhãn và phản hồi action đa ngôn ngữ của trang kế hoạch.
- `frontend/lib/i18n-core.ts` — typed contract của workspace translation keys.
- `frontend/tests/i18n.test.mjs` — contract tests cho workspace actions và translation coverage.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/components/PlanView.tsx` — thêm save action rõ ràng và thẻ tổng quan lấy dữ liệu live từ plan/ngày active, dùng chung share/regenerate hiện có.
- [x] `frontend/app/globals.css` — tạo layout card giống mẫu ở desktop/mobile, gồm hero, facts, stop summary và action bar.
- [x] `frontend/lib/i18n-core.ts` + `frontend/lib/workspace-translations.ts` — bổ sung nhãn Save/saved và các copy cần thiết cho toàn bộ locale mà không phá typed contract.
- [x] `frontend/tests/i18n.test.mjs` — khóa ba action, offline failure/success, regenerate guard và translation completeness.

**Acceptance Criteria:**
- Given một plan hợp lệ, when trang `/plan/[token]` mở, then đầu trang có thẻ tổng quan gồm ảnh/fallback, tiêu đề, facts và danh sách điểm dừng theo ngày active.
- Given người dùng đổi tab ngày, when active day thay đổi, then nội dung điểm dừng trong thẻ cập nhật theo cùng `slots` với workspace.
- Given người dùng bấm “Lưu kế hoạch”, when localStorage ghi thành công hoặc thất bại, then UI phản hồi đúng mà không gọi network.
- Given người dùng bấm “Chia sẻ”, when browser hỗ trợ hoặc không hỗ trợ Web Share, then hành vi native share/copy link hiện tại vẫn hoạt động.
- Given người dùng bấm “Tạo lại”, when request đang chạy, then nút bị disable và chỉ một regenerate request được phép; khi lỗi plan cũ còn nguyên.
- Given viewport mobile, when thẻ render, then action bar và danh sách không tràn ngang, touch target đủ rõ.

## Spec Change Log

## Design Notes

Thẻ tổng quan là lớp “glanceable summary”, không thay thế workspace. Ảnh ưu tiên slot đầu của ngày active có `anh`; fallback dùng gradient/illustration CSS. Danh sách điểm dừng hiển thị giờ bắt đầu và tên, còn mô tả/nguồn/đổi điểm vẫn ở workspace. Các action chính xuất hiện trong thẻ; nhóm công cụ nâng cao hiện tại có thể giữ trong header để tránh mất chức năng.

## Verification

**Commands:**
- `npm test` trong `frontend` — expected: toàn bộ tests pass.
- `npx tsc --noEmit` trong `frontend` — expected: không có lỗi TypeScript.

**Manual checks:**
- Mở plan có ảnh và plan thiếu ảnh; kiểm tra Save, Share, Regenerate và responsive ở 390px.

## Suggested Review Order

**Thẻ tổng quan và hành động**

- Entry point render dữ liệu live, ảnh fallback và ba hành động chính.
  [`PlanView.tsx:126`](frontend/components/PlanView.tsx#L126)

- Save ghi snapshot rõ ràng; Share và Regenerate tái sử dụng guard cũ.
  [`PlanView.tsx:105`](frontend/components/PlanView.tsx#L105)

- URL ảnh được kiểm tra trước render và lỗi được nhớ theo URL.
  [`PlanView.tsx:30`](frontend/components/PlanView.tsx#L30)

**Giao diện responsive**

- Card, facts, stop list và action bar bám cấu trúc ảnh mẫu.
  [`globals.css:37`](frontend/app/globals.css#L37)

- Text dài và RTL dùng logical positioning, tránh tràn mobile.
  [`globals.css:48`](frontend/app/globals.css#L48)

**Bản dịch và kiểm thử**

- Typed contract bổ sung bốn nhãn summary mới.
  [`i18n-core.ts:9`](frontend/lib/i18n-core.ts#L9)

- Catalog cung cấp đầy đủ copy cho toàn bộ locale.
  [`workspace-translations.ts:26`](frontend/lib/workspace-translations.ts#L26)

- Tests khóa cấu trúc card, Save và translation coverage.
  [`i18n.test.mjs:147`](frontend/tests/i18n.test.mjs#L147)
