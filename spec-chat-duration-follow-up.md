---
title: 'Hỏi bổ sung thời lượng trong hội thoại Planner'
type: 'feature'
created: '2026-08-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '2230c48017fc9d12afe0b6b3547becbc6efc2e36'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Khi yêu cầu đầu tiên không chứa thời lượng, Planner hiện in câu hỏi bổ sung như một dòng trạng thái bên dưới ô nhập. Người dùng phải tự hiểu rằng cần sửa lại nội dung cũ, nên trải nghiệm chưa giống chatbot và có nguy cơ làm mất yêu cầu ban đầu.

**Approach:** Hiển thị yêu cầu và câu hỏi bổ sung thành các bong bóng hội thoại. Khi chatbot đang chờ thời lượng, người dùng có thể trả lời trong ô chat hoặc bấm một trong bốn gợi ý “Vài giờ”, “Nửa ngày”, “Cả ngày”, “Nhiều ngày”; Planner giữ nguyên yêu cầu ban đầu, ghép dữ liệu đã thu thập và chỉ tạo kế hoạch sau khi có lựa chọn hợp lệ.

## Boundaries & Constraints

**Always:** Giữ nguyên API generate, SSE, nonce, timeout, xác thực, trường số người và ngân sách mặc định hiện có. Câu hỏi thời lượng và bốn nút gợi ý phải nằm trong luồng chat, hỗ trợ bàn phím/accessibility, và câu trả lời hoặc lựa chọn không được thay thế nội dung yêu cầu ban đầu.

**Ask First:** Mọi thay đổi yêu cầu backend hội thoại mới, bổ sung trường bắt buộc khác, bỏ input số người, hoặc thay đổi ngân sách mặc định.

**Never:** Gọi API khi chưa xác định được thời lượng; gửi riêng câu trả lời “nửa ngày” làm `context` và đánh mất ý định ban đầu; dựng chatbot giả phụ thuộc vào AI/network để hỏi câu cố định; làm hỏng quick-action, retry hoặc trạng thái busy hiện tại.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Đủ thời lượng ngay | “Đi cà phê cả ngày” | Hiện bubble người dùng và bắt đầu tạo kế hoạch ngay | Giữ luồng lỗi hiện có |
| Thiếu thời lượng | “Muốn đi cà phê và ăn ngon” | Hiện bubble người dùng, sau đó bubble chatbot hỏi thời lượng; chưa gọi API | Ô nhập chuyển sang chờ câu trả lời |
| Trả lời hợp lệ | Đang chờ + “Nửa ngày” | Hiện bubble trả lời, ghép với yêu cầu gốc và gọi API với `nua_ngay` | Không mất nội dung ban đầu |
| Chọn gợi ý | Đang chờ + bấm “Nửa ngày” | Xử lý giống hệt một câu trả lời hợp lệ, hiện bubble người dùng và gọi API với `nua_ngay` | Nút bị vô hiệu hóa khi request đang chạy |
| Trả lời chưa rõ | Đang chờ + “Tùy bạn” | Chatbot hỏi lại thời lượng trong bubble | Không gọi API, không báo lỗi chung |
| Chọn quick action | Người dùng bấm một gợi ý | Gợi ý đi vào ô nhập như hiện tại và lịch sử hội thoại cũ được reset phù hợp | Không để trạng thái chờ cũ chi phối yêu cầu mới |

</frozen-after-approval>

## Code Map

- `frontend/components/Planner.tsx` — quản lý input, suy luận thời lượng, submit và render Planner.
- `frontend/app/globals.css` — style bubble/message và layout chat hiện có.
- `frontend/components/LocaleProvider.tsx` — bản dịch câu chào và nhãn Planner hiện có.
- `frontend/tests/i18n.test.mjs` — contract source-level cho submit, timeout và các guard của Planner.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/components/Planner.tsx` — thêm trạng thái hội thoại cục bộ, tách yêu cầu gốc khỏi câu trả lời follow-up, render bubble, bốn nút gợi ý thời lượng và điều phối submit hai bước.
- [x] `frontend/app/globals.css` — bổ sung style tối thiểu cho transcript trong Planner, responsive và không phá bubble workspace.
- [x] `frontend/tests/i18n.test.mjs` — kiểm tra guard không gọi generate khi thiếu thời lượng, bảo toàn yêu cầu gốc và hỏi lại khi câu trả lời không hợp lệ.

**Acceptance Criteria:**
- Given yêu cầu chưa có thời lượng, when người dùng gửi, then yêu cầu và câu hỏi thời lượng xuất hiện theo thứ tự trong transcript chatbot và API chưa được gọi.
- Given chatbot đang chờ thời lượng, when người dùng trả lời hợp lệ, then Planner giữ ý định ban đầu, render câu trả lời và gửi request với duration tương ứng.
- Given chatbot đang chờ thời lượng, when người dùng bấm một gợi ý, then lựa chọn được render như câu trả lời của người dùng và tạo request với enum tương ứng.
- Given câu trả lời follow-up không suy ra được thời lượng, when người dùng gửi, then chatbot hỏi lại mà không tạo kế hoạch.
- Given yêu cầu ban đầu đã chứa thời lượng, when người dùng gửi, then Planner không hỏi thừa và giữ luồng tạo kế hoạch hiện tại.
- Given người dùng bàn phím hoặc screen reader, when hội thoại cập nhật, then transcript có live-region phù hợp và input vẫn có label.

## Spec Change Log

## Design Notes

Transcript chỉ cần tồn tại trong phiên component hiện tại; không lưu backend. Các nút gợi ý gọi chung một đường xử lý với câu trả lời text để tránh hai hành vi khác nhau. `context` gửi tới API là yêu cầu gốc, có thể nối câu trả lời thời lượng để giữ đầy đủ ngữ nghĩa, trong khi `thoi_luong` vẫn là enum đã suy ra bằng logic deterministic hiện có.

## Verification

**Commands:**
- `npm test` trong `frontend` — expected: toàn bộ test pass.
- `npx tsc --noEmit` trong `frontend` — expected: không có lỗi TypeScript.

**Manual checks:**
- Gửi yêu cầu không có thời lượng, trả lời “Nửa ngày”, xác nhận bubble đúng thứ tự và chỉ tạo plan sau câu trả lời.

## Suggested Review Order

**Luồng hội thoại**

- Entry point tách yêu cầu gốc và điều phối câu trả lời follow-up.
  [`Planner.tsx:183`](frontend/components/Planner.tsx#L183)

- Transcript và nhóm gợi ý render đúng thứ tự, hỗ trợ accessibility.
  [`Planner.tsx:246`](frontend/components/Planner.tsx#L246)

- Request giữ context gốc, duration enum và cơ chế retry hiện tại.
  [`Planner.tsx:99`](frontend/components/Planner.tsx#L99)

**Trình bày**

- Transcript tự cuộn, giới hạn chiều cao và responsive trên mobile.
  [`globals.css:19`](frontend/app/globals.css#L19)

**Kiểm thử**

- Contract test khóa trạng thái chờ, bảo toàn context và bốn mapping.
  [`i18n.test.mjs:247`](frontend/tests/i18n.test.mjs#L247)
