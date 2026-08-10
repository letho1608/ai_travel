---
title: 'Khớp icon Thay đổi và màu popup'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
review_loop_iteration: 0
context: []
---

# Khớp icon Thay đổi và màu popup

## Intent

**Problem:** Icon Thay đổi chưa thể hiện đúng hai đường uốn lượn giao nhau trong mẫu và popup chưa đủ nổi bật.

**Approach:** Dùng SVG hai tuyến shuffle liên tục, đồng bộ độ dày với icon Xóa và tô cả popup Thay đổi/Xóa bằng token xanh nhạt thích ứng sáng/tối.

## Suggested Review Order

**Visual fidelity**

- Hai đường shuffle liên tục giao nhau và có đầu mũi tên hướng phải.
  [`PlanView.tsx:248`](frontend/components/PlanView.tsx#L248)

- Token xanh đồng bộ hai popup và vẫn thích ứng dark mode.
  [`globals.css:67`](frontend/app/globals.css#L67)

**Regression contract**

- Khóa đầy đủ path SVG và token màu popup.
  [`i18n.test.mjs:192`](frontend/tests/i18n.test.mjs#L192)
