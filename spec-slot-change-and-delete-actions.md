---
title: 'Thêm thao tác thay đổi và xóa cho từng điểm lịch trình'
type: 'feature'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '4e4f71df56391837d936cf9f560f939a0fe130c8'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Mỗi điểm trong lịch trình hiện chỉ có icon đổi tự động, không giải thích lựa chọn và không cho người dùng xóa hoặc chọn rõ địa điểm thay thế.

**Approach:** Thiết kế hai nút “Thay đổi” và “Xóa” trên từng card. “Thay đổi” mở menu gồm đổi tự động bằng AI hoặc tìm/chọn một địa điểm cụ thể; “Xóa” yêu cầu xác nhận rồi cập nhật lịch trình ngay, đồng thời mọi thay đổi tạo phiên bản mới để có thể hoàn tác.

## Boundaries & Constraints

**Always:** Menu thay đổi phải gắn với đúng card và dùng được bằng bàn phím/screen reader. Đổi tự động tái sử dụng thuật toán swipe hiện có. Đổi cụ thể phải hiển thị gợi ý tìm kiếm và gửi ID chuẩn, không tự chọn mơ hồ từ text. Địa điểm thay thế phải chưa có trong lịch, phù hợp giờ của slot, ngân sách và các kiểm tra lịch hiện hữu. Nút Xóa chỉ hiển thị icon thùng rác giống mẫu nhưng phải có accessible label/tooltip; sau xác nhận, xóa đúng một slot và cập nhật tổng chi phí, selection/map, phiên bản cùng thông báo thành công. Cả replace/delete dùng optimistic version, owner/session authorization và giữ lịch cũ khi lỗi.

**Ask First:** Tự động dồn lại toàn bộ giờ sau khi xóa, xóa luôn ngày trống, hoặc cho phép chọn địa điểm ngoài catalog.

**Never:** Không xóa không xác nhận; không thay bằng tên mơ hồ; không phá dữ liệu hội thoại/version; không ghi đè thay đổi bản dịch Việt hiện có `regenerate: "Yêu cầu AI tạo lại lịch trình khác"`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Đổi tự động | Chọn “AI tự động thay đổi” | Thay đúng một điểm tương tự, giữ slot và tạo version | Không có candidate: giữ lịch, báo lỗi |
| Đổi cụ thể | Nhập tên, chọn một suggestion chuẩn | Thay đúng điểm bằng ID đã chọn | Không dùng text chưa chọn; target trùng/đóng cửa: báo lỗi |
| Xóa điểm | Xác nhận xóa trên card | Xóa đúng slot, cập nhật chi phí/map/version | Hủy xác nhận: không request; stale version: giữ lịch |
| Xóa khi lịch ở số slot tối thiểu | Điểm hợp lệ và thuộc lịch | Vẫn cho xóa theo ý người dùng | Bỏ qua riêng minimum slot count, giữ mọi validation khác |
| Lỗi mạng/API | Request thất bại | Card và lịch cũ không đổi | Hiển thị toast lỗi, cho thử lại |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — state/menu/search, gọi API và đồng bộ plan/map/version.
- `frontend/app/globals.css` — bố cục hai nút, popover và responsive styling.
- `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — nhãn, hướng dẫn, xác nhận và feedback đa ngôn ngữ.
- `backend/app/schemas.py` — payload thay cụ thể, tìm kiếm và xóa có validation.
- `backend/app/routers/plans.py` — search candidates, mở rộng swipe và endpoint xóa.
- `backend/app/pipeline/planner.py` — cho phép validation giữ constraints nhưng bỏ riêng minimum count sau xóa.
- `backend/tests/test_api.py`, `backend/tests/test_pipeline.py`, `frontend/tests/i18n.test.mjs` — regression API, validation và UI contract.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas.py`, `backend/app/routers/plans.py` — thêm search ID chuẩn, explicit replacement và delete có owner/version/rate-limit.
- [x] `backend/app/pipeline/planner.py` — hỗ trợ validation sau delete mà chỉ nới minimum slot count.
- [x] `frontend/components/PlanView.tsx`, `frontend/app/globals.css` — hai nút/card, accessible choice menu, suggestions, confirm delete và state sync.
- [x] `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — thêm copy cho toàn bộ locale, giữ nguyên override Việt hiện có.
- [x] `backend/tests/test_api.py`, `backend/tests/test_pipeline.py`, `frontend/tests/i18n.test.mjs` — kiểm tra success/error/stale/authorization/version và UI bindings.

**Acceptance Criteria:**
- Given một card, when mở “Thay đổi”, then đúng hai lựa chọn xuất hiện và focus/ARIA công bố được menu.
- Given người dùng chọn AI, when API thành công, then đúng một địa điểm được thay và map/version/selection cập nhật.
- Given người dùng tìm và chọn suggestion, when xác nhận, then ID cụ thể thay đúng slot hoặc lịch cũ được giữ nếu validation lỗi.
- Given người dùng xác nhận Xóa, when API thành công, then đúng slot biến mất, chi phí/version/map cập nhật và Undo có thể khôi phục.

## Spec Change Log

- 2026-08-10: Implemented canonical replacement search, explicit/AI replacement, optimistic delete with relaxed minimum cardinality, accessible card actions, translations, styling, and verification.

## Design Notes

Tìm kiếm trả danh sách nhỏ gồm `id`, tên, loại và khu vực; UI bắt buộc chọn suggestion để tránh tên trùng. Endpoint delete dùng validator hiện tại với cờ bỏ riêng minimum cardinality, không bỏ trusted ID, uniqueness, chronology, hours, travel hay budget.

## Verification

**Commands:**
- `pytest tests/test_api.py tests/test_pipeline.py -q` trong `backend` — API và pipeline pass.
- `npm test` và `npx tsc --noEmit` trong `frontend` — contract/i18n/typecheck pass.
- `git diff --check` — diff sạch.

## Suggested Review Order

**Luồng giao diện**

- Điểm vào chính cho menu thay đổi, tìm kiếm, xóa và đồng bộ phiên bản.
  [`PlanView.tsx:128`](frontend/components/PlanView.tsx#L128)

- Kiểu dáng hai hành động, popover và danh sách gợi ý trên từng card.
  [`globals.css:63`](frontend/app/globals.css#L63)

**Quy tắc backend**

- Một bộ lọc dùng chung bảo đảm gợi ý và thay thế có cùng điều kiện.
  [`plans.py:338`](backend/app/routers/plans.py#L338)

- Search, explicit/AI replacement và delete giữ authorization cùng optimistic version.
  [`plans.py:383`](backend/app/routers/plans.py#L383)

- Delete chỉ nới số slot tối thiểu, vẫn giữ các validation còn lại.
  [`planner.py:1398`](backend/app/pipeline/planner.py#L1398)

- Schema bổ sung ID thay thế chuẩn và payload xóa có phiên bản.
  [`schemas.py:48`](backend/app/schemas.py#L48)

**Bản dịch và kiểm thử**

- Copy Việt/Anh có fallback cho mọi locale, giữ nguyên câu Tạo lại đã chọn.
  [`workspace-translations.ts:50`](frontend/lib/workspace-translations.ts#L50)

- Regression API bảo vệ search, replace, delete và restore phiên bản.
  [`test_api.py:191`](backend/tests/test_api.py#L191)

- Regression pipeline khóa phạm vi nới validation sau khi xóa.
  [`test_pipeline.py:360`](backend/tests/test_pipeline.py#L360)
