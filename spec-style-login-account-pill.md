---
title: 'Thiết kế nút đăng nhập dạng tài khoản'
type: ui
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Thiết kế nút đăng nhập dạng tài khoản

## Intent

**Problem:** Nút đăng nhập trên thanh điều hướng chưa có kiểu pill xanh và icon tài khoản giống mẫu giao diện.

**Approach:** Giữ nguyên liên kết và nội dung dịch hiện tại, bổ sung icon người dùng dạng nét, nền xanh Hà Nội, chữ trắng in hoa, bo tròn hoàn toàn, hover đồng bộ và hiển thị thích ứng ở chế độ tối/mobile.

## Suggested Review Order

1. [Navigation.tsx](frontend/components/Navigation.tsx#L44) — cấu trúc nút và icon tài khoản, không đổi hành vi đăng nhập.
2. [globals.css](frontend/app/globals.css#L4) — hình dáng pill, màu sắc, responsive và trạng thái hover/dark mode.
3. [i18n.test.mjs](frontend/tests/i18n.test.mjs#L40) — hợp đồng kiểm tra cấu trúc và giao diện nút.
