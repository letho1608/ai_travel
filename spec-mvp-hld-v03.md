---
title: 'MVP Mình Đi Đâu Thế theo HLD v0.3'
type: 'feature'
created: '2026-08-05'
status: 'in-progress'
baseline_commit: 'NO_VCS'
review_loop_iteration: 2
context:
  - 'D:/AILearning/AI_Travel1/2.HLD_Research_Team_Report (1).md'
  - 'D:/AILearning/AI_Travel1/1.PRD_Research_Team_Reports.md'
  - 'D:/AILearning/AI_Travel1/Baocao.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Kho làm việc mới chỉ có tài liệu; chưa có ứng dụng MVP để tạo, lưu, chia sẻ và điều chỉnh lịch trình Hà Nội. PRD cũ còn mâu thuẫn với HLD về số phương án và cách dùng AI.

**Approach:** Phát triển monorepo Next.js + FastAPI qua ba giai đoạn: hoàn thiện nền tảng HLD v0.3 bằng dữ liệu thật; xây workspace chat–itinerary–map và vòng đời chuyến đi; sau đó đạt capability parity với Layla.ai về planning, live travel inventory, collaboration và assisted booking. Không sao chép mã, thương hiệu hoặc tài sản độc quyền của Layla.

## Boundaries & Constraints

**Always:** HLD v0.3 thắng với phần lõi Hà Nội; parity mở rộng được thêm theo yêu cầu ngày 2026-08-05. Dữ liệu địa điểm, thời tiết, giá và availability phải có nguồn thật và provenance. Các ràng buộc định lượng do code kiểm tra; AI không được bịa inventory. Chia sẻ mặc định chỉ đọc; mutation cần quyền chủ sở hữu; rate limit, cost ledger và persistence phải bền vững/fail-closed. Giao diện mobile-first, tiếng Việt UTF-8, accessibility và privacy-by-design.

**Ask First:** Cần khóa thật, tài khoản cloud, triển khai Internet, gửi email thật, Google OAuth production, gọi AI trả phí, tải dữ liệu OSM/OSRM lớn hoặc thay đổi các quyết định kiến trúc đã chốt.

**Never:** Bịa địa điểm/giá/availability; để AI tự tính đường hoặc tin dữ liệu không kiểm chứng; sao chép mã nguồn, thương hiệu, văn bản, hình ảnh hay thiết kế độc quyền của Layla; nhúng bí mật vào repo; tuyên bố booking đã hoàn tất khi chưa có xác nhận từ nhà cung cấp; render HTML chưa làm sạch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Tạo kế hoạch | Bối cảnh tiếng Việt, vị trí, thời lượng, phiên hợp lệ | SSE trạng thái rồi trả một kế hoạch 4–6 điểm, token chia sẻ và bản đồ | 400 cho dữ liệu sai; 429 quá giới hạn; 503 khi AI/bộ đếm/bảng khoảng cách không sẵn sàng |
| Xem chia sẻ | Token còn hạn | Trang SSR chỉ đọc có metadata và lịch/bản đồ | 404 khi thiếu hoặc hết hạn |
| Vuốt đổi điểm | Chủ sở hữu, phiên bản hiện tại | Thay đúng một điểm cùng loại/tuyến; cập nhật hồ sơ tag; tăng phiên bản | 401/403 sai chủ; 409 xung đột; 404 không có điểm thay |
| Làm lại | Chủ sở hữu và nonce mới | Tạo một kế hoạch mới, bỏ qua cache | Áp dụng rate limit và lỗi pipeline như tạo mới |
| Đăng nhập | Google token hợp lệ và mã phiên ẩn danh | Gộp kế hoạch/hồ sơ, xóa ngày hết hạn | Không thu thập quyền ngoài email/tên; 401 token sai |
| AI trả sai | Timeout, JSON lỗi hoặc địa điểm ngoài danh sách | Thử lại giới hạn, kiểm tra và sửa bằng code | Hard-abort 30 giây; 503 nếu không có phương án an toàn |

</frozen-after-approval>

## Code Map

- `frontend/` — Next.js, Tailwind, trang chủ/login/history/plan, SSE client và Leaflet.
- `backend/app/` — FastAPI routers, schemas, services, models và pipeline xác định.
- `backend/alembic/` — migration PostgreSQL theo mô hình dữ liệu HLD.
- `backend/data/` — bộ dữ liệu mẫu Hà Nội và bảng khoảng cách phục vụ local/test.
- `backend/tests/` — unit, pipeline và API integration tests.
- `frontend/tests/` — component và luồng giao diện trọng yếu.
- `.github/workflows/ci.yml` — lint, test và build hai ứng dụng.
- `docker-compose.yml` — PostgreSQL/Redis local; không chứa bí mật.

## Tasks & Acceptance

**Execution:**
- [x] Dựng cấu trúc monorepo, cấu hình môi trường mẫu, Docker local và CI.
- [x] Tạo schema/migration cho địa điểm, khoảng cách, kế hoạch, hồ sơ, nhật ký, người dùng, consent và chi phí AI.
- [x] Xây pipeline tìm ứng viên, chấm điểm, nearest-neighbor + 2-opt, gán giờ, validation, repair và AI JSON adapter/mock.
- [x] Xây API tạo/xem/vuốt/làm lại/lịch sử/xác thực, SSE, quyền sở hữu, khóa lạc quan, rate limit, cache và circuit breaker.
- [x] Tạo seed Hà Nội đủ chạy demo và cổng chặn metadata bảng khoảng cách.
- [x] Xây giao diện responsive: nhập nhu cầu, tiến trình, một timeline, bản đồ, chia sẻ, vuốt/đổi, lịch sử và trạng thái lỗi.
- [x] Thêm nhắc trong ứng dụng, hook email tùy chọn, analytics chuẩn và dọn dữ liệu hết hạn.
- [x] Viết kiểm thử cho matrix, thuật toán, bảo mật và build production; bổ sung README vận hành/PoC.

**Acceptance Criteria:**
- Given dịch vụ local và seed hợp lệ, when người dùng tạo kế hoạch, then luồng hoàn tất với đúng một lịch trình khả thi và mọi địa điểm thuộc seed.
- Given kế hoạch được chia sẻ, when người khác mở token, then họ xem được metadata/lịch/bản đồ nhưng không sửa được.
- Given AI chưa cấu hình, when chạy local/test, then adapter giả lập vẫn tạo kết quả xác định mà không phát sinh mạng hoặc chi phí.
- Given bảng khoảng cách hoặc bộ đếm chi phí không đọc được, when tạo/làm lại, then hệ thống fail-closed và không gọi AI.
- Given toàn bộ mã nguồn, when chạy lint, test và production build, then mọi bước hoàn tất thành công.

## Spec Change Log

- Vòng 1: Review phát hiện runtime chỉ dùng memory, không có AI adapter/circuit breaker, SSE bị buffer, duration/budget/giờ mở cửa sai, swipe dựng lại cả lịch, OAuth không ổn định và nhiều UI chỉ là placeholder. Tasks được siết thành runtime adapter phải fail-closed ngoài local, pipeline phải test đủ bốn duration/ngân sách/chronology, mutation phải đúng một điểm/idempotent, SSE phải đọc theo chunk, và UI phải gọi API thật. Tránh trạng thái biết build nhưng mất dữ liệu/bảo vệ sau restart. KEEP: giao diện responsive hiện tại, schema tiếng Việt, thuật toán route, SSR metadata, migration, CI và các test đang xanh.
- Vòng 2: Yêu cầu mới mở rộng mục tiêu thành đầy đủ ba giai đoạn và capability parity với Layla.ai bằng dữ liệu thật. Frozen intent được người dùng trực tiếp renegotiate. Spec bổ sung live inventory, collaboration, booking handoff và UX workspace; vẫn cấm sao chép tài sản Layla hoặc tạo dữ liệu giả. KEEP: một kế hoạch tối ưu cho luồng HLD Hà Nội, deterministic validation, privacy và fail-closed.

## Design Notes

Triển khai theo contract-first và dependency injection để PostgreSQL/Redis/AI thật có thể thay bằng adapter local trong kiểm thử. PoC tuần 1 được cung cấp dưới dạng script và tài liệu vận hành; việc gọi dịch vụ/triển khai thật vẫn cần người dùng cấp quyền theo mục Ask First.

## Verification

**Commands:**
- `docker compose config` — cấu hình local hợp lệ.
- `cd backend && pytest && ruff check .` — backend và pipeline đạt.
- `cd frontend && npm test && npm run lint && npm run build` — frontend đạt.

**Manual checks:**
- Chạy hành trình tạo → xem bản đồ → chia sẻ → vuốt đổi → làm lại trên màn hình desktop và mobile.

## Suggested Review Order

**Roadtrip / Multi-city**

- Roadtrip validates bounded OSRM streams, all snapped waypoints, endpoint geometry, route totals, provenance and expiry before exposing a live route.
  [`roadtrip.py:18`](backend/app/services/roadtrip.py#L18)

- Multi-city persists only bounded, fresh and structurally valid live inventory snapshots; incomplete provider coverage stays explicit.
  [`multicity.py:18`](backend/app/services/multicity.py#L18)

- Route and inventory UIs share the same session, cancel stale locale requests, reject mismatched response cardinality and support all 19 locales.
  [`page.tsx:20`](frontend/app/roadtrip/page.tsx#L20)

**Live Inventory / Explore**

- Explore validates bounded provider responses, snapshot expiry, duplicate offers, currencies, timezone-aware transfers and booking-assistance races.
  [`page.tsx:18`](frontend/app/explore/page.tsx#L18)

- Inventory routes enforce IP plus session rate limits before calling a provider.
  [`inventory.py:16`](backend/app/routers/inventory.py#L16)

- Both runtime stores reject expired snapshots and deduplicate booking-assistance requests; PostgreSQL serializes concurrent creates.
  [`postgres_store.py:217`](backend/app/services/postgres_store.py#L217)

- Adapter failures from malformed live payloads are normalized to the controlled unavailable boundary.
  [`inventory.py:15`](backend/app/services/inventory.py#L15)

- The typed Inventory catalog covers all 19 locales and restores interpolation placeholders to the canonical contract.
  [`inventory-translations.ts:1`](frontend/lib/inventory-translations.ts#L1)

**Localized trip lifecycle**

- Persisted locale drives deterministic itinerary copy, live weather, AI prompts and every plan mutation.
  [`planner.py:26`](backend/app/pipeline/planner.py#L26)

- PDF and calendar exports preserve the stored plan language with localized metadata and labels.
  [`pdf_export.py:25`](backend/app/services/pdf_export.py#L25)

- Weather responses are bounded, freshness-stamped and localized from validated WMO facts.
  [`weather.py:1`](backend/app/services/weather.py#L1)

- Entry point validates API contracts, async states, ownership actions and accessibility.
  [`page.tsx:11`](frontend/app/history/page.tsx#L11)

- Typed 19-locale catalog makes missing UI copy fail at build time.
  [`LocaleProvider.tsx:7`](frontend/components/LocaleProvider.tsx#L7)

- Locale normalization keeps translation, document language and RTL direction consistent.
  [`LocaleProvider.tsx:36`](frontend/components/LocaleProvider.tsx#L36)

**Durable reminder semantics**

- Memory notifications expose structured trip titles instead of localized persisted prose.
  [`store.py:342`](backend/app/services/store.py#L342)

- PostgreSQL joins the same structured title for parity across runtime stores.
  [`postgres_store.py:520`](backend/app/services/postgres_store.py#L520)

**Verification**

- Tests execute production normalization/interpolation and enforce complete locale catalogs.
  [`i18n.test.mjs:13`](frontend/tests/i18n.test.mjs#L13)

**Localized and consent-safe login**

- Login entry point freezes consent per request and rejects unsafe OAuth responses.
  [`page.tsx:36`](frontend/app/login/page.tsx#L36)

- Production builds fail closed instead of exposing the local mock login.
  [`page.tsx:20`](frontend/app/login/page.tsx#L20)

- Typed login catalog supplies complete legal and failure copy across 19 locales.
  [`LocaleProvider.tsx:33`](frontend/components/LocaleProvider.tsx#L33)

- Contract test rejects missing or empty login translations in every locale.
  [`i18n.test.mjs:22`](frontend/tests/i18n.test.mjs#L22)

**Localized and identity-safe settings**

- Settings validates preference contracts and separates authenticated from anonymous identity.
  [`page.tsx:13`](frontend/app/settings/page.tsx#L13)

- Inline destructive confirmation remains accessible and preserves deletion outcome semantics.
  [`page.tsx:36`](frontend/app/settings/page.tsx#L36)

- Invalid bearer tokens now fail closed instead of falling back to anonymous preferences.
  [`auth.py:91`](backend/app/routers/auth.py#L91)

- Runtime key lists drive complete, nonblank and nonduplicated catalog tests.
  [`i18n-core.ts:5`](frontend/lib/i18n-core.ts#L5)

**Localized Planner entry point**

- Home and Planner render typed copy for all 19 locales while preserving the generation payload.
  [`Planner.tsx:8`](frontend/components/Planner.tsx#L8)

- Planner owns duplicate-submit, 30-second timeout, unmount cancellation, safe result validation and accessible form state.
  [`Planner.tsx:14`](frontend/components/Planner.tsx#L14)

- SSE parsing accepts LF/CRLF, flushes a final block and rejects malformed or duplicate events.
  [`api.ts:27`](frontend/lib/api.ts#L27)

- Shared session fallback preserves owner actions when browser storage is unavailable.
  [`session.ts:13`](frontend/lib/session.ts#L13)

- Contract tests pin catalog completeness, status mappings, payload and real CRLF stream behavior.
  [`i18n.test.mjs:70`](frontend/tests/i18n.test.mjs#L70)

**Localized and owner-safe Plan Workspace**

- Workspace mutations validate deep response shapes, combine bearer/session ownership and reject stale route generations.
  [`PlanView.tsx:44`](frontend/components/PlanView.tsx#L44)

- Native slot selection avoids nested interactive controls while preserving map/timeline synchronization.
  [`PlanView.tsx:76`](frontend/components/PlanView.tsx#L76)

- Dedicated 19-locale catalog covers 51 workspace keys without English fallback.
  [`workspace-translations.ts:4`](frontend/lib/workspace-translations.ts#L4)

- Backend swipe now supports every trip day; ICS export folds UTF-8 lines and includes required timestamps.
  [`plans.py:111`](backend/app/routers/plans.py#L111)

- Multi-day API tests prove day-two replacement and complete calendar export.
  [`test_api.py:41`](backend/tests/test_api.py#L41)

- Frontend contracts verify locale completeness, placeholders, timeout, ownership headers and token-generation guards.
  [`i18n.test.mjs:57`](frontend/tests/i18n.test.mjs#L57)
