---
title: 'Nhận diện chợ đêm thiếu tag từ dữ liệu OSM'
type: 'bugfix'
created: '2026-08-10'
status: 'done'
route: 'one-shot'
---

# Nhận diện chợ đêm thiếu tag từ dữ liệu OSM

## Intent

**Problem:** Bản ghi OSM “Chợ Đêm Hàng Đào – Đồng Xuân” chỉ có tag `attraction` và giờ mở cửa 07:00, nên không được nhận diện là chợ đêm và vẫn bị xếp lúc 10:11.

**Approach:** Với địa điểm loại `cho`, nhận diện thêm cụm tên chuẩn hóa “chợ đêm”/“night market”, đồng bộ route ordering và hard floor 18:00; không nhận nhầm nhà hàng chỉ nhắc tới chợ đêm trong tên.

## Suggested Review Order

**Runtime classification**

- Route markets recognized from provider names into the evening segment.
  [`planner.py:504`](backend/app/pipeline/planner.py#L504)

- Restrict name fallback to market-kind records and generic semantic phrases.
  [`planner.py:515`](backend/app/pipeline/planner.py#L515)

**Regression coverage**

- Exercise the exact OSM record, both modes, English names, and restaurant exclusion.
  [`test_pipeline.py:144`](backend/tests/test_pipeline.py#L144)
