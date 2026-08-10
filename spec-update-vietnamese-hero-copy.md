---
title: 'Cập nhật mô tả hero tiếng Việt'
type: 'chore'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
---

# Cập nhật mô tả hero tiếng Việt

## Intent

**Problem:** Nội dung mô tả hero tiếng Việt chưa dùng thông điệp mới do người dùng cung cấp.

**Approach:** Thay duy nhất giá trị `heroLead` tiếng Việt bằng câu mới, giữ nguyên các locale và nội dung khác.

## Suggested Review Order

- Xác nhận câu hero tiếng Việt khớp nguyên văn yêu cầu.
  [`LocaleProvider.tsx:75`](frontend/components/LocaleProvider.tsx#L75)
