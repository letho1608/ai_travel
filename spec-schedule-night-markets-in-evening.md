---
title: 'Xếp chợ đêm đúng vào buổi tối'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 1
baseline_commit: '55d171773867420526ef1bf16e9350aae08aa666'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Điểm chợ đêm đôi khi bị xếp vào buổi sáng vì nhánh giảm thời gian chờ có thể bỏ qua khung ưu tiên 18:00.

**Approach:** Chỉ coi các điểm có tag `cho_dem` hoặc `night_market` là ràng buộc thời gian cứng từ 18:00; các địa danh phố cổ/nightlife dùng được cả ngày vẫn giữ lịch linh hoạt.

## Boundaries & Constraints

**Always:** Chợ đêm phải bắt đầu từ 18:00 trở đi trong cả chế độ thường và `relax`; vẫn tôn trọng giờ mở/đóng cửa, thời lượng tối thiểu, thời gian di chuyển và giới hạn ngày.

**Ask First:** Mở rộng ràng buộc sang toàn bộ tag `nightlife`, điểm mở sau 17:00 hoặc thay dữ liệu catalog.

**Never:** Không hard-code tên riêng từng chợ; không đổi thuật toán chọn địa điểm, API hoặc frontend.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Chợ đêm mở cả ngày | Tag `cho_dem` hoặc `night_market`, mở từ sáng | Slot bắt đầu từ 18:00 | Nếu không đủ thời gian buổi tối thì bỏ candidate |
| Chế độ relax | Scheduler thử nới khung giờ | Vẫn không kéo chợ đêm về ban ngày | Trả `None` nếu không còn khung tối |
| Địa danh nightlife dùng cả ngày | Chỉ có tag `nightlife`, không phải chợ đêm | Giữ hành vi hiện tại | Không bị ép sang tối |

</frozen-after-approval>

## Code Map

- `backend/app/pipeline/planner.py` — nhận diện chợ đêm và tính giới hạn slot.
- `backend/tests/test_pipeline.py` — kiểm thử hồi quy thời gian chợ đêm.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/pipeline/planner.py` — áp dụng hard floor 18:00 cho `cho_dem`/`night_market` trong normal và relax.
- [x] `backend/tests/test_pipeline.py` — kiểm tra riêng từng tag, trường hợp không đủ giờ và bảo toàn nightlife ban ngày.

**Acceptance Criteria:**
- Given chợ đêm mở từ sáng, when tính slot normal hoặc relax, then bắt đầu không sớm hơn 18:00.
- Given không đủ thời lượng sau 18:00, when tính slot, then candidate bị bỏ thay vì chuyển sang buổi sáng.
- Given điểm chỉ có tag `nightlife`, when tính slot ban ngày, then hành vi hiện tại được giữ nguyên.

## Spec Change Log

- 2026-08-10: Human narrowed the rule to `cho_dem` and `night_market`; preserved daytime behavior for dual-use nightlife landmarks.
- 2026-08-10: Implemented the narrowed rule with a dedicated night-market predicate; verified 30 pipeline tests and planner compilation.
- 2026-08-10: Review extended the hard floor to meal-classified markets and added regression coverage for that path.

## Design Notes

Ràng buộc phải nằm trong `_compute_slot_bounds`, là ranh giới cuối trước khi tạo slot. `_is_evening_place` vẫn có nghĩa rộng hơn cho route ordering nên cần predicate chợ đêm riêng để không làm thay đổi các điểm mở muộn khác.

## Verification

**Commands:**
- `pytest tests/test_pipeline.py -q` trong `backend` — toàn bộ pipeline tests pass.
- `python -m compileall app/pipeline/planner.py` trong `backend` — module hợp lệ.

## Suggested Review Order

**Night-market invariant**

- Isolate exact market tags without changing general nightlife routing.
  [`planner.py:515`](backend/app/pipeline/planner.py#L515)

- Give market hours precedence over meal and guidance windows.
  [`planner.py:786`](backend/app/pipeline/planner.py#L786)

- Enforce the 18:00 floor at the final scheduling boundary.
  [`planner.py:909`](backend/app/pipeline/planner.py#L909)

**Regression coverage**

- Cover both tags, normal, relax, and meal-classified markets.
  [`test_pipeline.py:103`](backend/tests/test_pipeline.py#L103)

- Reject markets when the remaining evening window is too short.
  [`test_pipeline.py:144`](backend/tests/test_pipeline.py#L144)

- Preserve daytime scheduling for nightlife-only landmarks.
  [`test_pipeline.py:169`](backend/tests/test_pipeline.py#L169)
