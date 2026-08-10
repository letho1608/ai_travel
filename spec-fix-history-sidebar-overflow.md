---
title: 'Sửa tràn danh sách Lịch sử'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
---

# Sửa tràn danh sách Lịch sử

## Intent

**Problem:** Tiêu đề kế hoạch dài trong sidebar Lịch sử mở rộng flex item, khiến chữ và mũi tên tràn sang vùng thẻ nội dung.

**Approach:** Giới hạn sidebar/link theo chiều rộng cột, cho phần tiêu đề co và ellipsis trong khi mũi tên giữ kích thước; duy trì danh sách cuộn ngang 210px trên mobile mà không cắt focus outline.

## Suggested Review Order

**Giới hạn layout**

- Khóa flex item trong sidebar và bảo toàn mũi tên.
  [`globals.css:50`](frontend/app/globals.css#L50)

- Duy trì dải cuộn ngang trên màn hình nhỏ.
  [`globals.css:51`](frontend/app/globals.css#L51)

**Bảo vệ hồi quy**

- Kiểm tra cấu trúc markup, ellipsis, chevron và mobile scrolling.
  [`i18n.test.mjs:249`](frontend/tests/i18n.test.mjs#L249)
