---
title: 'Sửa phản hồi Lưu kế hoạch và tạo lại lịch trình'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '83cd806369b029ac4e0003725bb99faa0a277123'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Sau khi bấm Lưu kế hoạch, thông báo được render ở đầu workspace nên người dùng đang ở cuối thẻ không nhìn thấy. Nút Làm lại có thể timeout trước khi backend hoàn tất và phương án trả về thường gần như giống kế hoạch cũ, khiến thao tác có vẻ không hoạt động.

**Approach:** Hiển thị phản hồi hành động dưới dạng toast luôn nằm trong vùng nhìn, đồng thời cho thao tác Làm lại thời gian xử lý phù hợp và yêu cầu backend tạo một phương án khác rõ ràng so với lịch trình hiện tại. Khi thành công, giao diện phải cập nhật kế hoạch và thông báo đúng ngữ nghĩa “đã tạo lại”.

## Boundaries & Constraints

**Always:** Lưu đúng payload kế hoạch/version hiện tại vào localStorage; toast thành công hoặc lỗi phải có live-region, nhìn thấy ngay và tự đóng hợp lý. Làm lại phải giữ nguyên yêu cầu ban đầu, token và chuỗi phiên bản, chống gửi trùng bằng nonce, nhưng thay đổi tập địa điểm so với kế hoạch cũ khi đủ dữ liệu. Kế hoạch hiện tại phải được giữ nguyên nếu backend trả lỗi hoặc timeout.

**Ask First:** Thay đổi API công khai, chuyển regenerate sang job bất đồng bộ, hoặc thay đổi schema kế hoạch.

**Never:** Không giả lập thành công khi chưa lưu hoặc chưa nhận kế hoạch hợp lệ. Không thay đổi logic lập kế hoạch thông thường, swipe/refine, lịch sử phiên bản, chia sẻ hoặc bản đồ. Không dùng nội dung mẫu cố định để tạo cảm giác kế hoạch đã đổi.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Lưu thành công | localStorage khả dụng | Payload hiện tại được lưu và toast “Đã lưu kế hoạch” xuất hiện cạnh viewport | Tự đóng sau khoảng thời gian hiện có |
| Lưu thất bại | Trình duyệt chặn/quota localStorage | Không crash; toast lỗi nhìn thấy ngay | Giữ nguyên kế hoạch |
| Làm lại thành công | Kế hoạch hợp lệ và catalog đủ điểm thay thế | Backend tăng version; UI hiển thị phương án có tập điểm khác và toast thành công | Reset ngày/điểm đang chọn về dữ liệu mới |
| Làm lại chậm | Pipeline mất hơn 30 giây nhưng vẫn trong giới hạn regenerate | Client tiếp tục chờ và cập nhật khi hoàn tất | Sau giới hạn riêng mới báo lỗi |
| Không đủ phương án mới | Catalog/provider không tạo được kế hoạch khác | API trả lỗi rõ ràng; UI hiện toast lỗi | Không thay kế hoạch cũ |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — timeout request, state message, handler Lưu/Làm lại và vị trí render phản hồi.
- `frontend/app/globals.css` — style status hiện tại và layout thẻ lịch trình; cần toast cố định responsive.
- `frontend/lib/i18n-core.ts` — contract khóa dịch cho thông báo thành công Làm lại.
- `frontend/lib/workspace-translations.ts` — nội dung phản hồi đa ngôn ngữ.
- `backend/app/routers/plans.py` — endpoint regenerate hiện chỉ loại điểm đầu tiên của kế hoạch cũ.
- `backend/tests/test_api.py` — kiểm thử regenerate/version/nonce và tính khác biệt của phương án.
- `frontend/tests/i18n.test.mjs` — contract frontend hiện mới kiểm tra regex cơ bản.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/components/PlanView.tsx` — thêm toast accessible, timeout riêng cho regenerate và thông báo thành công đúng ngữ nghĩa.
- [x] `frontend/app/globals.css` — định dạng toast cố định, rõ ràng trên desktop/mobile và không che thao tác chính.
- [x] `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — thêm khóa `regenerateSuccess` đầy đủ cho mọi locale.
- [x] `backend/app/routers/plans.py` — loại các địa điểm của kế hoạch cũ khi làm lại để tạo phương án thực sự khác, giữ nonce/version/token.
- [x] `backend/tests/test_api.py`, `frontend/tests/i18n.test.mjs` — bảo vệ khác biệt lịch trình, timeout riêng, toast Lưu/Làm lại và phản hồi lỗi.

**Acceptance Criteria:**
- Given người dùng đang ở cuối thẻ lịch trình, when bấm Lưu kế hoạch, then toast thành công hoặc lỗi xuất hiện ngay trong viewport và được screen reader công bố.
- Given pipeline hoàn tất sau hơn 30 giây nhưng chưa quá giới hạn regenerate, when bấm Làm lại, then UI vẫn nhận và hiển thị kế hoạch mới.
- Given regenerate thành công, when so sánh trước và sau, then version tăng, token giữ nguyên và tập địa điểm thay đổi; UI hiển thị thông báo tạo lại thành công.
- Given regenerate thất bại, when lỗi được trả về, then kế hoạch hiện tại không đổi và toast lỗi nhìn thấy ngay.

## Spec Change Log

## Design Notes

Toast là phản hồi toàn cục của hành động nhưng phải nằm cố định ở cạnh dưới viewport để vẫn thấy khi panel đang cuộn. Regenerate nên ưu tiên loại toàn bộ ID cũ; nếu dữ liệu không đủ để tạo phương án hợp lệ thì báo lỗi thay vì trả một bản gần như không đổi.

## Verification

**Commands:**
- `npm test` trong `frontend` — toàn bộ frontend contract pass.
- `npx tsc --noEmit` trong `frontend` — không lỗi TypeScript.
- `pytest tests/test_api.py -k regenerate -q` trong `backend` — các test regenerate trực tiếp pass và xác nhận kế hoạch khác.

**Manual checks:**
- Trên trang kế hoạch có dữ liệu, cuộn xuống cuối và bấm Lưu/Làm lại; kiểm tra toast, trạng thái disabled trong lúc chạy, nội dung/version/địa điểm sau khi thành công và kế hoạch cũ khi lỗi.

## Suggested Review Order

**Luồng hành động trên giao diện**

- Timeout riêng và phản hồi đúng khi nhận phương án mới.
  [`PlanView.tsx:93`](frontend/components/PlanView.tsx#L93)

- Toast phân biệt thành công/lỗi và luôn nằm trong viewport.
  [`PlanView.tsx:126`](frontend/components/PlanView.tsx#L126)

- Style responsive, reduced-motion và màu trạng thái rõ ràng.
  [`globals.css:11`](frontend/app/globals.css#L11)

**Tạo phương án mới**

- Loại địa điểm cũ trước khi chạy lại pipeline.
  [`plans.py:422`](backend/app/routers/plans.py#L422)

**Đa ngôn ngữ và kiểm thử**

- Cung cấp phản hồi thành công cho toàn bộ locale.
  [`workspace-translations.ts:26`](frontend/lib/workspace-translations.ts#L26)

- Bảo vệ token, version và tập địa điểm mới.
  [`test_api.py:217`](backend/tests/test_api.py#L217)

- Bảo vệ toast, timeout và contract bản dịch frontend.
  [`i18n.test.mjs:160`](frontend/tests/i18n.test.mjs#L160)
