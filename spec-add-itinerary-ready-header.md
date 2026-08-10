---
title: 'Thêm phần trạng thái hoàn tất lịch trình'
type: 'feature'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
review_loop_iteration: 0
context: []
---

# Thêm phần trạng thái hoàn tất lịch trình

## Intent

**Problem:** Màn hình lịch trình thiếu nút quay về hội thoại và tín hiệu rõ ràng rằng hệ thống đã hoàn tất tạo kế hoạch.

**Approach:** Thêm nút Trở lại chat và thẻ AI đã tạo xong phía trên nội dung hiện hữu; nút cuộn/focus chat đang có để giữ nguyên lịch trình và mọi trạng thái.

## Suggested Review Order

**Result experience**

- Nút quay về đúng chat hiện tại và thẻ hoàn tất đứng trước nội dung cũ.
  [`PlanView.tsx:225`](frontend/components/PlanView.tsx#L225)

- Kiểu dáng xanh responsive tái hiện hierarchy của mẫu.
  [`globals.css:69`](frontend/app/globals.css#L69)

**Localization and contracts**

- Copy mới có fallback Anh và bản địa hóa tiếng Việt.
  [`workspace-translations.ts:55`](frontend/lib/workspace-translations.ts#L55)

- Test bảo vệ hành vi scroll/focus và cấu trúc phần trạng thái.
  [`i18n.test.mjs:196`](frontend/tests/i18n.test.mjs#L196)
