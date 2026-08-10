---
title: 'Thay định dạng khu vực lịch trình bằng thẻ kế hoạch mới'
type: 'refactor'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '2230c48017fc9d12afe0b6b3547becbc6efc2e36'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Trang kế hoạch hiện hiển thị thẻ tóm tắt mới ở phía trên nhưng vẫn giữ khối “Lịch trình” cũ bên dưới, khiến cùng một lịch trình xuất hiện hai lần và giao diện không đúng mẫu đã duyệt.

**Approach:** Bỏ bản tóm tắt độc lập ở đầu trang và áp dụng ngôn ngữ thiết kế của thẻ mới trực tiếp cho khối lịch trình trong workspace. Đây chỉ là thay đổi JSX/CSS frontend; thuật toán, API, dữ liệu và nội dung chi tiết của lịch trình được giữ nguyên.

## Boundaries & Constraints

**Always:** Giữ nguyên dữ liệu `plan`, thứ tự ngày/địa điểm, cách chọn ngày và điểm, bản đồ đồng bộ, ảnh và fallback, thời gian bắt đầu/kết thúc, nhãn bữa ăn, tên, mô tả, chi phí, ghi chú, nguồn và thao tác đổi địa điểm. Đặt Lưu kế hoạch, Chia sẻ và Tạo lại trong khu vực lịch trình mới; giữ nguyên hành vi hiện có của từng nút. Giữ nguyên chat, bản đồ, các thao tác ở header và khả năng responsive.

**Ask First:** Bất kỳ thay đổi nào cần sửa backend, schema/API, thuật toán tạo/xếp lịch trình, nội dung do hệ thống sinh, hoặc loại bỏ một thao tác/dữ liệu đang hiển thị.

**Never:** Không tạo thêm một bản sao/tóm tắt lịch trình ở nơi khác. Không thay dữ liệu thật bằng nội dung mẫu trong ảnh. Không đổi logic lưu, chia sẻ, tạo lại, swipe, chọn điểm hoặc chọn ngày.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Kế hoạch hợp lệ | Một hoặc nhiều ngày với các điểm đầy đủ | Chỉ có một khu vực lịch trình theo giao diện thẻ mới; mọi nội dung chi tiết và thao tác cũ vẫn xuất hiện | N/A |
| Nhiều ngày | Người dùng đổi tab ngày | Thẻ lịch trình hiển thị đúng các điểm của ngày đang chọn và bản đồ/selection tiếp tục đồng bộ | Giữ cơ chế clamp/reset hiện có |
| Ảnh thiếu hoặc lỗi | Điểm đại diện/điểm dừng không có ảnh hợp lệ | Giao diện dùng fallback và không làm hỏng layout | Không crash khi render |
| Nội dung dài hoặc màn hình hẹp | Tên/mô tả/nguồn dài trên mobile | Nội dung wrap, nút thao tác sử dụng được và không tràn ngang | Responsive xuống một cột khi cần |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — chứa thẻ tóm tắt mới đang bị lặp và khối lịch trình chi tiết cần định dạng lại.
- `frontend/app/globals.css` — chứa style của summary card, workspace, day tabs và slot cũ.
- `frontend/tests/i18n.test.mjs` — kiểm tra cấu trúc giao diện kế hoạch và nhãn hành động đa ngôn ngữ.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/components/PlanView.tsx` — hợp nhất summary card vào `itinerary-panel`, loại bỏ bản sao phía trên và giữ nguyên đầy đủ nội dung/handler của từng điểm.
- [x] `frontend/app/globals.css` — điều chỉnh layout thẻ, hero, tab ngày, danh sách điểm và action bar cho desktop/mobile mà không ảnh hưởng chat/map.
- [x] `frontend/tests/i18n.test.mjs` — cập nhật assertion để bảo vệ việc chỉ có một khu vực lịch trình và vẫn có Lưu/Chia sẻ/Tạo lại cùng nội dung chi tiết.

**Acceptance Criteria:**
- Given trang kế hoạch đã tải, when người dùng xem workspace, then chỉ thấy một khu vực lịch trình và khu vực đó dùng định dạng thẻ mới.
- Given dữ liệu lịch trình hiện tại, when giao diện mới render, then thời gian, ảnh, nhãn bữa ăn, tên, mô tả, chi phí, ghi chú, nguồn và nút đổi địa điểm vẫn được hiển thị/hoạt động.
- Given người dùng đổi ngày hoặc chọn một điểm, when state thay đổi, then danh sách và bản đồ tiếp tục đồng bộ như trước.
- Given người dùng chọn Lưu kế hoạch, Chia sẻ hoặc Tạo lại, when thao tác hoàn tất hoặc lỗi, then hành vi và phản hồi vẫn giống logic hiện có.
- Given màn hình mobile, when nội dung dài, then thẻ không tràn ngang và các nút vẫn dễ thao tác.

## Spec Change Log

## Design Notes

Ảnh mẫu là định hướng hình thức, không phải nguồn dữ liệu. Hero/facts/action bar tạo khung nhận diện của thẻ mới; bên dưới vẫn phải giữ danh sách điểm chi tiết hiện có thay vì rút gọn còn thời gian và tên điểm.

## Verification

**Commands:**
- `npm test` trong `frontend` — toàn bộ test pass.
- `npx tsc --noEmit` trong `frontend` — không có lỗi TypeScript.

**Manual checks:**
- Kiểm tra desktop và mobile: không có lịch trình lặp; tab ngày, chọn điểm, swipe, Lưu, Chia sẻ và Tạo lại vẫn hoạt động; chat và bản đồ không đổi chức năng.

## Suggested Review Order

**Cấu trúc lịch trình**

- Hợp nhất hero, ngày, chi tiết điểm và hành động vào một panel duy nhất.
  [`PlanView.tsx:130`](frontend/components/PlanView.tsx#L130)

**Trình bày responsive**

- Định dạng thẻ mới trong workspace và giữ danh sách dài cuộn trên desktop.
  [`globals.css:40`](frontend/app/globals.css#L40)

- Xếp action thành một cột và bỏ giới hạn cuộn trên mobile.
  [`globals.css:38`](frontend/app/globals.css#L38)

**Bảo vệ hồi quy**

- Xác nhận chỉ còn một panel và nội dung chi tiết không bị mất.
  [`i18n.test.mjs:159`](frontend/tests/i18n.test.mjs#L159)
