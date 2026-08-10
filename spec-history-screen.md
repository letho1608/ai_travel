---
title: 'Đổi Chuyến đi thành màn Lịch sử theo ảnh mẫu'
type: 'feature'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '2230c48017fc9d12afe0b6b3547becbc6efc2e36'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Tab `/history` hiện mang nhãn “Chuyến đi” và chỉ hiển thị danh sách đơn giản, chưa giống màn lịch sử kế hoạch trong ảnh tham chiếu mà người dùng cung cấp.

**Approach:** Đổi nhãn tiếng Việt của tab thành “Lịch sử”, đồng thời tổ chức lại trang `/history` thành bố cục lịch sử responsive gồm thanh bên, tiêu đề/bộ lọc và lưới thẻ kế hoạch. Tiếp tục dùng dữ liệu thật từ API và giữ nguyên hành vi thông báo, trạng thái tải, lỗi và rỗng.

## Boundaries & Constraints

**Always:** Chỉ sửa `Navigation`, bản dịch liên quan, trang `/history` và CSS có namespace riêng cho màn lịch sử; giữ nguyên API, xác thực, cấu trúc `Plan`, route chi tiết và các thay đổi chưa commit khác. Giao diện phải hoạt động trên desktop lẫn mobile và dùng dữ liệu kế hoạch hiện có.

**Ask First:** Bất kỳ yêu cầu nào cần đổi response backend, thêm trường dữ liệu mới, thêm route, hoặc thay đổi cấu trúc điều hướng ngoài việc đổi nhãn tab lịch sử.

**Never:** Ghi đè hoặc hoàn tác các chỉnh sửa đang có trong `globals.css`; hard-code các chuyến đi giả để thay cho dữ liệu API; sao chép pixel tuyệt đối khiến trang vỡ trên màn hình nhỏ; loại bỏ trạng thái loading/error/empty/notification.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Có kế hoạch | API trả một hoặc nhiều `StoredPlan` hợp lệ | Thanh bên và lưới thẻ hiển thị tiêu đề, ngày/thời lượng/chi phí khi có, mô tả và liên kết chi tiết | Trường tùy chọn thiếu được ẩn hoặc dùng nhãn trung tính, không làm vỡ layout |
| Không có kế hoạch | API trả danh sách rỗng | Hiển thị empty state và nút tạo kế hoạch mới | Không dựng thẻ mẫu giả |
| API lỗi | Request plans hoặc notifications thất bại | Giữ trang ổn định và thông báo lỗi hiện có | Không che mất lỗi bằng layout mới |
| Màn hình nhỏ | Viewport tablet/mobile | Thanh bên xếp trên nội dung, bộ lọc cuộn/xuống dòng, thẻ thành một cột | Không tràn ngang |

</frozen-after-approval>

## Code Map

- `frontend/components/Navigation.tsx` — render nhãn tab và trạng thái active của `/history`.
- `frontend/components/LocaleProvider.tsx` — nguồn bản dịch `trips`, trong đó tiếng Việt cần đổi thành “Lịch sử”.
- `frontend/app/history/page.tsx` — tải plans/notifications và render toàn bộ màn lịch sử.
- `frontend/app/globals.css` — chứa style toàn cục; bổ sung khối `.history-*` biệt lập để hạn chế xung đột.
- `frontend/lib/types.ts` — kiểu `Plan` hiện có, cung cấp tiêu đề, tóm tắt, ngày đi, thời lượng và chi phí.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/components/LocaleProvider.tsx` — đổi bản dịch `vi.trips` sang “Lịch sử” để tab và các vị trí tái sử dụng có nhãn đúng.
- [x] `frontend/app/history/page.tsx` — tái cấu trúc markup theo ảnh mẫu, thêm bộ lọc phía client và trình bày metadata an toàn từ `Plan`, nhưng giữ nguyên fetch/mutation/error semantics.
- [x] `frontend/app/globals.css` — thêm style responsive, trạng thái selected/filter/status và card actions dưới namespace `.history-*`, không sửa/xóa phần thay đổi có sẵn.
- [x] `frontend/tests/i18n.test.mjs` — cập nhật hoặc bổ sung assertion cho nhãn tiếng Việt nếu test hiện tại bao phủ khóa này.

**Acceptance Criteria:**
- Given locale tiếng Việt, when thanh điều hướng hiển thị, then route `/history` có nhãn “Lịch sử” và active đúng khi người dùng mở trang.
- Given danh sách kế hoạch hợp lệ, when `/history` render, then giao diện có thanh “Lịch sử kế hoạch”, tiêu đề “Kế hoạch của bạn”, nhóm bộ lọc và lưới thẻ gần với ảnh mẫu.
- Given người dùng chọn một bộ lọc, when danh sách được lọc, then kết quả cập nhật phía client và nút được chọn có trạng thái trực quan lẫn `aria-pressed`.
- Given màn hình hẹp, when trang render, then nội dung chuyển về một cột mà không tràn ngang.
- Given loading, lỗi hoặc dữ liệu rỗng, when trạng thái tương ứng xảy ra, then thông báo/empty state hiện hành vẫn hoạt động.

## Spec Change Log

## Design Notes

Ảnh mẫu là định hướng bố cục và phân cấp thị giác, không phải nguồn dữ liệu. Vì model hiện tại không có trạng thái “hoàn thành/dự định” hay category chuẩn hóa, UI chỉ suy ra nhóm “Gần đây/Dự định” từ `ngay_di` khi parse được; bộ lọc không có dữ liệu đáng tin sẽ không được giả lập. Các metadata như ngày, thời lượng và chi phí chỉ hiển thị khi dữ liệu thật sẵn có.

## Verification

**Commands:**
- `npm test` trong `frontend` — expected: toàn bộ Node tests pass.
- `npm run build` trong `frontend` — expected: Next.js build và TypeScript hoàn tất không lỗi.

**Manual checks (if no CLI):**
- Mở `http://localhost:3001/history`, đối chiếu desktop với ảnh mẫu và thu nhỏ viewport để xác nhận responsive.

## Suggested Review Order

**Luồng dữ liệu và giao diện**

- Entry point giữ fetch cũ và dựng màn lịch sử mới từ dữ liệu thật.
  [`page.tsx:39`](frontend/app/history/page.tsx#L39)

- Bố cục sidebar, bộ lọc và lưới thẻ bám theo ảnh mẫu.
  [`page.tsx:110`](frontend/app/history/page.tsx#L110)

- Parse ngày nghiêm ngặt tránh phân loại sai dữ liệu không hợp lệ.
  [`page.tsx:26`](frontend/app/history/page.tsx#L26)

**Trình bày và responsive**

- Namespace lịch sử cô lập style desktop, card và trạng thái bộ lọc.
  [`globals.css:37`](frontend/app/globals.css#L37)

- Breakpoint mobile chuyển một cột và ngăn tràn ngang.
  [`globals.css:39`](frontend/app/globals.css#L39)

**Nhãn và kiểm thử**

- Nhãn điều hướng tiếng Việt đổi chính xác thành “Lịch sử”.
  [`LocaleProvider.tsx:12`](frontend/components/LocaleProvider.tsx#L12)

- Regression test khóa nhãn tiếng Việt và contract history hiện hữu.
  [`i18n.test.mjs:219`](frontend/tests/i18n.test.mjs#L219)
