---
title: 'Sửa popup lịch trình bị cắt và icon Thay đổi'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
review_loop_iteration: 0
context: []
---

# Sửa popup lịch trình bị cắt và icon Thay đổi

## Intent

**Problem:** Popup thao tác vẫn bị ancestor của timeline cắt một phần và icon Thay đổi chưa đúng hình shuffle trong mẫu.

**Approach:** Render cả popup Thay đổi và Xóa trực tiếp dưới `document.body` bằng portal, đồng thời dùng glyph shuffle hai luồng liên tục với đầu mũi tên bo tròn.

## Suggested Review Order

**Popup rendering**

- Portal tách overlay khỏi mọi overflow và transform của card lịch trình.
  [`PlanView.tsx:267`](frontend/components/PlanView.tsx#L267)

**Icon fidelity**

- Glyph shuffle chuẩn giữ hai tuyến liên tục ở kích thước nút nhỏ.
  [`PlanView.tsx:248`](frontend/components/PlanView.tsx#L248)

**Regression contract**

- Khóa body portal cho hai popup và toàn bộ bốn path của icon.
  [`i18n.test.mjs:188`](frontend/tests/i18n.test.mjs#L188)
