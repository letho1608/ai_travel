---
title: 'Thêm nút đóng popup Thay đổi'
type: 'feature'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
review_loop_iteration: 0
context: []
---

# Thêm nút đóng popup Thay đổi

## Intent

**Problem:** Popup Thay đổi thiếu nút đóng trực quan nên người dùng không rõ cách thoát.

**Approach:** Thêm nút X ở góc trên theo hướng locale, dùng chung luồng đóng với Escape/click ngoài, dọn trạng thái tìm kiếm và trả focus về nút mở.

## Suggested Review Order

**Interaction**

- Một hàm đóng thống nhất dọn state và khôi phục focus an toàn.
  [`PlanView.tsx:116`](frontend/components/PlanView.tsx#L116)

- Nút X có accessible label riêng và icon SVG không được screen reader đọc.
  [`PlanView.tsx:277`](frontend/components/PlanView.tsx#L277)

**Presentation and copy**

- Nút đóng neo theo hướng locale và giữ vùng bấm 34px.
  [`globals.css:68`](frontend/app/globals.css#L68)

- Copy đóng popup được typed và có bản Việt/Anh.
  [`workspace-translations.ts:53`](frontend/lib/workspace-translations.ts#L53)

**Regression contract**

- Khóa wiring nút đóng và vị trí logic theo RTL.
  [`i18n.test.mjs:194`](frontend/tests/i18n.test.mjs#L194)
