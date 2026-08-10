---
title: 'Cập nhật icon và màu nút lịch trình'
type: 'feature'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
---

# Cập nhật icon và màu nút lịch trình

## Intent

**Problem:** Nút Lưu và Chia sẻ dùng ký hiệu tạm, màu chưa giống mẫu; nhãn tiếng Việt của nút tạo phương án khác vẫn là “Làm lại”.

**Approach:** Dùng icon bookmark và share dạng nút nối bằng SVG, áp dụng màu xanh/trắng và nền trung tính theo ảnh mẫu, đồng thời đổi nhãn tiếng Việt thành “Tạo lại”.

## Suggested Review Order

**Giao diện hành động**

- Gắn màu và SVG theo vai trò primary/secondary của từng nút.
  [`globals.css:60`](frontend/app/globals.css#L60)

**Nhãn tiếng Việt**

- Ghi đè nhãn regenerate thành “Tạo lại” trong catalog runtime.
  [`workspace-translations.ts:26`](frontend/lib/workspace-translations.ts#L26)

**Bảo vệ hồi quy**

- Kiểm tra nhãn, màu và đúng loại SVG cho từng hành động.
  [`i18n.test.mjs:86`](frontend/tests/i18n.test.mjs#L86)
