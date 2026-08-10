---
status: done
route: one-shot
---

# Trở lại chat mở trang chat chính

## Intent

Nút **Trở lại chat** trên màn hình lịch trình luôn mở trang chủ `/`, nơi chứa chatbox lập kế hoạch. Nút không dùng lịch sử trình duyệt và không phụ thuộc trang mà người dùng đã mở lịch trình từ đó.

## Thay đổi

- [x] Cố định điều hướng của nút về `/` trong `frontend/components/PlanView.tsx`.
- [x] Thêm kiểm tra ngăn việc dùng lại `window.history.back()` trong `frontend/tests/i18n.test.mjs`.

## Xác minh

- [x] `npm test` — 22/22 đạt.
- [x] `npx tsc --noEmit` — đạt.
- [x] `git diff --check` — sạch (chỉ có cảnh báo chuyển đổi LF/CRLF của Git trên Windows).

