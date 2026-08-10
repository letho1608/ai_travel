---
title: 'Tinh gọn thao tác thay đổi và xóa địa điểm'
type: 'feature'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 1
baseline_commit: 'b1426517777eb52c3489ec09a9017e1432e5b219'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hai nút thao tác hiện chiếm không gian ngang của nội dung card, còn luồng chọn địa điểm bắt người dùng tìm rồi chọn lại trong danh sách gợi ý.

**Approach:** Đưa “Thay đổi” và icon Xóa xuống góc dưới bên trái card; hiển thị hai lựa chọn thay đổi trong popup nổi. Khi người dùng nhập tên, giao diện gợi ý địa điểm catalog; nếu họ không chọn gợi ý thì hệ thống dùng nguyên text để xác minh địa điểm ngoài catalog và thay thế.

## Boundaries & Constraints

**Always:** Hai nút nằm tách khỏi vùng text và neo ở đáy card, không che nội dung trên desktop/mobile. Popup nổi gắn đúng card, có focus, Escape, click ngoài để đóng và trả focus về nút mở. Lựa chọn AI tiếp tục dùng thuật toán thay tương tự. Khi nhập text, suggestion catalog xuất hiện để chọn nhanh; submit không chọn suggestion phải xác minh địa điểm thật tại Hà Nội qua OSM/Nominatim, lấy ID, tên, tọa độ và nguồn chuẩn trước khi thay. Nếu nguồn không có giờ mở cửa hoặc chi phí, AI được phép ước tính nhưng UI phải ghi rõ từng dữ liệu ước tính và nhắc người dùng kiểm tra lại. Địa điểm catalog hoặc ngoài catalog đều phải phù hợp khung giờ, di chuyển, ngân sách và chưa có trong lịch. Xóa vẫn xác nhận và giữ icon thùng rác/accessibility hiện tại.

**Ask First:** Tự chọn khi nhiều suggestion catalog trùng tên; chấp nhận địa điểm ngoài phạm vi Hà Nội hoặc nguồn xác minh không trả đủ tọa độ; dùng ước tính mà không công bố; đổi vị trí nút sang góc phải.

**Never:** Không lưu text thuần chưa được xác minh thành một slot; không lấy catalog suggestion đầu tiên khi tên mơ hồ; không thay đổi thuật toán AI, version/Undo hay hành vi Xóa.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| AI tự thay | Chọn lựa chọn 1 | Thay một địa điểm tương tự như hiện tại | Giữ lịch cũ và báo lỗi nếu không có ứng viên |
| Chọn gợi ý | Chọn một suggestion catalog | Thay bằng ID chuẩn đã chọn | Giữ lịch cũ nếu không còn hợp lệ |
| Nhập địa điểm ngoài catalog | Không chọn suggestion, text xác minh được trên OSM | Thay bằng địa điểm đã xác minh và hiển thị map/source | N/A |
| Thiếu giờ hoặc chi phí | OSM có địa điểm/tọa độ nhưng thiếu metadata | AI ước tính dữ liệu thiếu và đánh dấu rõ trên slot | Nếu AI không trả dữ liệu hợp lệ, giữ lịch cũ và báo lỗi |
| Tên không xác minh được | Text không khớp catalog/OSM | Không thay lịch | Báo không tìm thấy địa điểm |
| Tên catalog mơ hồ | Nhiều catalog record cùng tên chuẩn hóa và không chọn | Dùng nguyên text qua bước xác minh ngoài catalog | Không tự chọn ngầm một suggestion |
| Tên khớp nhưng không hợp lệ | Đóng cửa/trùng/vi phạm ngân sách hoặc di chuyển | Không thay lịch | Báo địa điểm không phù hợp |

</frozen-after-approval>

## Code Map

- `frontend/components/PlanView.tsx` — popup, form nhập tên trực tiếp và đồng bộ trạng thái.
- `frontend/app/globals.css` — neo cụm nút ở đáy trái và popup overlay responsive.
- `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — copy lỗi nhập tên trực tiếp.
- `backend/app/schemas.py` — payload tên địa điểm thay thế.
- `backend/app/routers/plans.py` — resolve tên duy nhất rồi tái sử dụng eligibility/replace hiện có.
- `backend/app/pipeline/planner.py` — validation nhận metadata địa điểm ngoài catalog đã xác minh.
- `backend/app/services/osm_verify.py` — xác minh địa điểm Hà Nội với tên Unicode ổn định.
- `backend/tests/test_api.py`, `backend/tests/test_pipeline.py`, `frontend/tests/i18n.test.mjs` — regression API, validation và UI contract.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/schemas.py`, `backend/app/routers/plans.py` — nhận text trực tiếp, xác minh OSM khi ngoài catalog và giữ eligibility/version.
- [x] `backend/app/pipeline/planner.py` — cho validator dùng metadata địa điểm ngoài catalog đã xác minh.
- [x] `frontend/components/PlanView.tsx` — giữ autocomplete suggestions nhưng cho phép submit nguyên text trong popup.
- [x] `frontend/app/globals.css` — bố trí cụm nút đáy trái và popup nổi không làm giãn card.
- [x] `frontend/lib/i18n-core.ts`, `frontend/lib/workspace-translations.ts` — cập nhật nhãn và phản hồi phù hợp.
- [x] `backend/tests/test_api.py`, `backend/tests/test_pipeline.py`, `frontend/tests/i18n.test.mjs` — khóa catalog/custom, xác minh thất bại và UI mới.

**Acceptance Criteria:**
- Given card có nội dung dài hoặc ngắn, when hiển thị, then text không bị cụm nút chiếm cột và nút nằm ở đáy trái.
- Given popup đang mở, when dùng bàn phím hoặc click ngoài, then focus/đóng popup hoạt động đúng.
- Given người dùng nhập text mà không chọn gợi ý, when submit, then địa điểm ngoài catalog được xác minh và thay trực tiếp.

## Spec Change Log

- 2026-08-10: Review phát hiện nguồn OSM có thể thiếu giờ mở cửa/chi phí; cần người dùng chọn chính sách cho metadata chưa biết trước khi triển khai lại. KEEP: bố cục nút đáy trái, popup, autocomplete catalog và đường submit text ngoài catalog.

## Design Notes

Backend ưu tiên ID suggestion đã chọn. Với text thuần, tái sử dụng `verify_place_name` để tìm catalog gần đúng hoặc Nominatim; kết quả xác minh được đưa tạm vào tập trusted/route validation của lần thay thế, không sửa catalog toàn cục. Trường dữ liệu OSM bị thiếu được AI điền theo schema giới hạn; slot lưu cờ/ghi chú ước tính để frontend luôn công bố nguồn gốc dữ liệu.

## Verification

**Commands:**
- `pytest tests/test_api.py tests/test_pipeline.py -q` trong `backend` — API và validation pass.
- `npm test` và `npx tsc --noEmit` trong `frontend` — UI contract/i18n/typecheck pass.
- `git diff --check` — diff sạch.

## Suggested Review Order

**Luồng thay địa điểm**

- Entry point xử lý ID gợi ý hoặc text ngoài catalog an toàn.
  [`plans.py:409`](backend/app/routers/plans.py#L409)

- Popup, autocomplete và submit text đồng bộ plan/version phía client.
  [`PlanView.tsx:129`](frontend/components/PlanView.tsx#L129)

- Cụm nút đáy trái và popup viewport tiết kiệm diện tích card.
  [`globals.css:64`](frontend/app/globals.css#L64)

**Xác minh và ước tính**

- Nominatim kiểm tra ambiguity, ID chuẩn và phạm vi Hà Nội.
  [`osm_verify.py:121`](backend/app/services/osm_verify.py#L121)

- AI estimate có schema giới hạn, circuit breaker và cost telemetry.
  [`ai.py:115`](backend/app/services/ai.py#L115)

- Validator nhận metadata external đã xác minh cho giờ và tuyến.
  [`planner.py:1399`](backend/app/pipeline/planner.py#L1399)

**Kiểm thử**

- API regression khóa nguồn OSM và nhãn dữ liệu AI ước tính.
  [`test_api.py:224`](backend/tests/test_api.py#L224)

- Pipeline regression khóa trusted metadata cho external place.
  [`test_pipeline.py:372`](backend/tests/test_pipeline.py#L372)
