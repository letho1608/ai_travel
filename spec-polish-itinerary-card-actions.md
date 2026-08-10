---
title: 'Hoàn thiện popup và thao tác trên card lịch trình'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '17a6f9be55f28adfd74d8105da9b26e641a9fe12'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Popup Thay đổi đang bị cắt một phần; cụm thao tác chưa đúng vị trí mong muốn và xác nhận Xóa dùng hộp thoại trình duyệt. Thuật toán AI thay thế cũng chưa ưu tiên đủ mạnh các địa điểm tương tự.

**Approach:** Chuyển cụm Thay đổi/Xóa xuống góc dưới phải, dùng icon shuffle giống mẫu, render các lựa chọn trong popup luôn nằm trọn viewport, và thay confirm trình duyệt bằng popup xác nhận neo cạnh icon Xóa. Xếp hạng AI replacement theo mức tương đồng trước rồi mới xét khoảng cách.

## Boundaries & Constraints

**Always:** Popup Thay đổi phải nhìn thấy đầy đủ ở mọi vị trí scroll và kích thước mobile/desktop, có Escape, click ngoài, focus/ARIA và trả focus đúng nút mở. Popup Xóa xuất hiện gần icon Xóa, nêu đúng tên địa điểm, có Hủy/Xóa, không gửi request trước khi xác nhận. Hai nút nằm góc dưới phải, không chiếm cột text. Icon Thay đổi là shuffle hai mũi tên bằng SVG, không dùng ký tự text. AI auto-replace ưu tiên cùng loại, nhiều tag chung và khu vực tương đồng trước khoảng cách; ứng viên vẫn phải qua giờ, ngân sách, di chuyển, uniqueness và version validation hiện có.

**Ask First:** Đổi màu/kích thước card ngoài phạm vi mẫu; thay đổi tiêu chí validation; cho phép xóa không xác nhận.

**Never:** Không dùng `window.confirm`; không để popup bị clip bởi timeline/card overflow; không làm suy yếu eligibility để lấy địa điểm “tương tự”; không thay đổi luồng nhập địa điểm catalog/ngoài catalog vừa hoàn thiện.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mở Thay đổi | Card ở đầu/cuối vùng scroll | Popup hiển thị đầy đủ trong viewport | Tự điều chỉnh vị trí nếu gần mép |
| AI tự thay | Có nhiều candidate hợp lệ | Chọn candidate tương tự nhất theo kind/tags/area rồi distance | Không có candidate: giữ lịch cũ |
| Mở Xóa | Click icon thùng rác | Popup xác nhận cạnh icon, focus vào Hủy/Xóa | Escape/click ngoài chỉ đóng popup |
| Xác nhận Xóa | Click Xóa trong popup | Gửi đúng một request và cập nhật plan/version | Lỗi API giữ lịch cũ |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — trạng thái, focus và hai popup trên từng card.
- `frontend/app/globals.css` — vị trí góc phải, popover viewport-safe và icon/action layout.
- `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — copy xác nhận Hủy/Xóa.
- `backend/app/routers/plans.py` — ranking candidate tương tự cho AI auto-replace.
- `backend/tests/test_api.py`, `frontend/tests/i18n.test.mjs` — regression ranking và UI contract.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/routers/plans.py` — rank candidate theo kind/tag/area/distance sau eligibility.
- [x] `frontend/components/PlanView.tsx` — icon shuffle SVG, delete confirmation popover và focus/dismiss logic.
- [x] `frontend/app/globals.css` — cụm nút dưới phải và hai popup không bị clipping.
- [x] `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — nhãn xác nhận xóa có fallback locale.
- [x] `backend/tests/test_api.py`, `frontend/tests/i18n.test.mjs` — bảo vệ ranking, không `window.confirm`, popup và icon.

**Acceptance Criteria:**
- Given card có text dài, when render, then cụm nút ở đáy phải và text dùng toàn bộ chiều ngang.
- Given popup mở gần mọi cạnh viewport, when hiển thị, then toàn bộ nội dung vẫn nhìn thấy và thao tác được.
- Given người dùng dùng bàn phím, when mở/đóng/xác nhận, then focus và accessible name đúng.

## Spec Change Log

## Design Notes

Ranking AI là tuple ổn định: cùng `kind` trước, số tag giao nhau giảm dần, cùng `area`, rồi khoảng cách. Popup Thay đổi có thể dùng modal fixed viewport để tránh ancestor clipping; popup Xóa nhỏ neo bằng tọa độ trigger và clamp trong viewport.

## Verification

**Commands:**
- `pytest tests/test_api.py -q` trong `backend` — replacement ranking pass.
- `npm test` và `npx tsc --noEmit` trong `frontend` — UI/i18n/typecheck pass.
- `git diff --check` — diff sạch.

## Suggested Review Order

**Replacement ranking**

- Ưu tiên độ tương đồng nhưng vẫn cho phép fallback khác loại hợp lệ.
  [`plans.py:408`](backend/app/routers/plans.py#L408)

- Khóa thứ tự kind, tag, khu vực và khoảng cách bằng regression test.
  [`test_api.py:224`](backend/tests/test_api.py#L224)

**Card actions and popups**

- Điều phối popup, neo viewport, focus và cập nhật sau khi xóa.
  [`PlanView.tsx:101`](frontend/components/PlanView.tsx#L101)

- Gắn hai thao tác ở góc phải và tránh clipping do transform/overflow.
  [`globals.css:62`](frontend/app/globals.css#L62)

**Copy and contracts**

- Bổ sung khóa dịch typed cho nút Hủy trong xác nhận xóa.
  [`i18n-core.ts:9`](frontend/lib/i18n-core.ts#L9)

- Cung cấp copy tiếng Việt và fallback tiếng Anh.
  [`workspace-translations.ts:50`](frontend/lib/workspace-translations.ts#L50)

- Bảo vệ icon SVG, popup fixed và loại bỏ browser confirm.
  [`i18n.test.mjs:186`](frontend/tests/i18n.test.mjs#L186)
