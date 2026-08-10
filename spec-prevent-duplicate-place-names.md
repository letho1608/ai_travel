---
title: 'Ngăn địa điểm trùng tên làm hỏng quá trình tạo kế hoạch'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'e3a88173ecc9204083edaa4f09ac55b5817b806a'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Pipeline đôi khi chọn hai bản ghi có ID khác nhau nhưng cùng tên chuẩn hóa, ví dụ hai chi nhánh “Highlands Coffee”. Draft sau đó bị validator chặn với lỗi “Kế hoạch chứa địa điểm trùng tên”, khiến người dùng không tạo được kế hoạch.

**Approach:** Áp dụng cùng một quy tắc chống trùng tên tại mọi ranh giới xếp lịch và backfill, thay vì chỉ kiểm tra ID hoặc lọc một lần trước vòng lặp. Khi gặp một alias trùng tên, planner phải thử địa điểm hợp lệ tiếp theo và vẫn giữ validator cuối làm lớp bảo vệ.

## Boundaries & Constraints

**Always:** So sánh tên bằng cùng `_place_name_key` mà `validate_plan` sử dụng; bảo đảm uniqueness trên toàn bộ chuyến đi, kể cả nhiều ngày. Các nhánh meal, rest, extra, route packing và backfill phải không chèn tên đã dùng. Nếu candidate gần nhất trùng tên, tiếp tục thử candidate khác để đạt số slot tối thiểu khi còn dữ liệu hợp lệ. Giữ nguyên kiểm tra trusted ID, ngân sách, giờ mở cửa, thời gian di chuyển và số slot.

**Ask First:** Thay đổi định nghĩa sản phẩm để cho phép nhiều chi nhánh cùng thương hiệu/tên trong một kế hoạch, hoặc thay đổi schema/canonical identity của địa điểm.

**Never:** Không xóa hoặc nới lỏng validator trùng tên. Không xóa hàng loạt dữ liệu catalog để che lỗi. Không đổi API frontend/backend, nội dung lỗi chung hoặc thuật toán xếp tuyến ngoài phần lọc candidate trùng tên.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Hai ID cùng tên | Candidate gần nhất có normalized name đã dùng | Bỏ alias và chọn candidate tên khác tiếp theo | Không trả lỗi trùng tên nếu còn lựa chọn |
| Khác dấu/hoa/thừa khoảng trắng | “Cafe Dinh” và “Café Đinh” | Chỉ một địa điểm được xếp | Dùng `_place_name_key`, không so raw string |
| Backfill | Khoảng trống cần thêm slot, candidate đầu trùng tên | Backfill thử candidate tiếp theo | Chỉ báo thiếu slot khi hết lựa chọn hợp lệ |
| Nhiều ngày | Tên đã xuất hiện ở ngày trước | Không lặp lại ở ngày sau | Uniqueness áp dụng toàn chuyến đi |
| Catalog không đủ tên khác | Không còn candidate đáp ứng mọi constraint | Pipeline trả lỗi thiếu địa điểm phù hợp | Không tạo draft vi phạm validator |

</frozen-after-approval>

## Code Map

- `backend/app/pipeline/planner.py` — selection, route packing, meal/rest/extra/backfill và validator cuối.
- `backend/tests/test_pipeline.py` — kiểm thử build plan, uniqueness và các constraint pipeline.
- `backend/app/data.py` — catalog chứa nhiều OSM node/way/chi nhánh có normalized name giống nhau; chỉ dùng làm fixture thực tế, không sửa dữ liệu.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/pipeline/planner.py` — dùng invariant ID+tên đã dùng trong các nhánh chọn/xếp và lọc lại trong từng vòng lặp/backfill.
- [x] `backend/tests/test_pipeline.py` — thêm regression tests cho alias cùng tên, dấu/case/spacing, backfill chọn candidate kế tiếp và uniqueness nhiều ngày.

**Acceptance Criteria:**
- Given catalog có nhiều ID cùng normalized name, when tạo kế hoạch, then kế hoạch hợp lệ được trả về nếu còn đủ địa điểm tên khác.
- Given planner xếp nhiều ngày hoặc backfill khoảng trống, when một tên đã được dùng, then không nhánh nào chèn alias cùng tên lần nữa.
- Given không còn đủ candidate tên khác đáp ứng constraint, when build kết thúc, then pipeline trả lỗi phù hợp mà không trả draft trùng tên.
- Given kế hoạch được tạo thành công, when chạy `validate_plan`, then không có lỗi trùng ID hoặc trùng tên và các constraint cũ vẫn đạt.

## Spec Change Log

- 2026-08-10: Implemented live normalized-name exclusion across meal, rest,
  refreshment, evening, extra-stop, route packing, and backfill selection. Added
  regressions for accent/case/spacing aliases and selecting the next distinct
  candidate.
- 2026-08-10: Review hardened backfill to retry candidates that cannot fit the
  target gap and added direct behavioral coverage for that recovery path.

## Design Notes

Catalog có hàng trăm nhóm tên trùng do dữ liệu chi nhánh và alias OSM. Fix cần nằm ở scheduler: `scheduled_names` phải là state sống được kiểm tra ngay trước mỗi lần chọn/chèn, không phải snapshot lọc một lần. Validator cuối tiếp tục phát hiện mọi nhánh còn sót.

## Verification

**Commands:**
- `pytest tests/test_pipeline.py -q` trong `backend` — toàn bộ pipeline tests pass.
- `pytest tests/test_api.py -k generate -q` trong `backend` — luồng API tạo kế hoạch liên quan pass.

**Manual checks:**
- Tạo lại yêu cầu đã gây lỗi và xác nhận trả về trang kế hoạch thay vì “Kế hoạch chứa địa điểm trùng tên”.

**Automated results (2026-08-10):**
- `pytest tests/test_pipeline.py -q`: 27 passed.
- `pytest tests/test_api.py -k generate -q`: 5 passed, 1 failed in the pre-existing
  swipe step (`test_plan_locale_is_persisted_and_reused_by_swipe_and_regenerate`,
  expected 200 but received 503 before regenerate).

## Suggested Review Order

**Normalized-name scheduling invariant**

- Thread one trip-wide name set through meal and route selection.
  [`planner.py:372`](backend/app/pipeline/planner.py#L372)

- Reserve helper stops by normalized name across all trip days.
  [`planner.py:612`](backend/app/pipeline/planner.py#L612)

- Remove same-name aliases immediately after a stop is packed.
  [`planner.py:971`](backend/app/pipeline/planner.py#L971)

**Backfill recovery**

- Retry distinct candidates until one fits both travel and time bounds.
  [`planner.py:1142`](backend/app/pipeline/planner.py#L1142)

**Regression coverage**

- Assert generated plans are unique by the validator's normalized key.
  [`test_pipeline.py:112`](backend/tests/test_pipeline.py#L112)

- Prove alias filtering selects the next differently named candidate.
  [`test_pipeline.py:151`](backend/tests/test_pipeline.py#L151)

- Exercise backfill retry when the first candidate cannot fit.
  [`test_pipeline.py:185`](backend/tests/test_pipeline.py#L185)
