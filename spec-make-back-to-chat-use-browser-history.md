---
title: 'Cho nút Trở lại chat quay về trang trước'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
review_loop_iteration: 0
context: []
---

# Cho nút Trở lại chat quay về trang trước

## Intent

**Problem:** Nút Trở lại chat đang cuộn đến chat trên cùng trang thay vì quay về trang người dùng vừa truy cập.

**Approach:** Dùng browser history để quay lại đúng entry trước đó; khi không có history thì điều hướng về trang chủ làm fallback.

## Suggested Review Order

**Navigation behavior**

- Handler ưu tiên browser back và chỉ dùng trang chủ khi không có history.
  [`PlanView.tsx:221`](frontend/components/PlanView.tsx#L221)

**Regression contract**

- Test khóa thứ tự điều kiện, back và fallback.
  [`i18n.test.mjs:211`](frontend/tests/i18n.test.mjs#L211)
