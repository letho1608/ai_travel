# Implementation Roadmap — HLD → Capability parity

## Definition of done

Mục tiêu chỉ hoàn tất khi từng capability có implementation, test, runtime evidence và nguồn dữ liệu thật. Giao diện được đánh giá theo usability/accessibility và capability parity, không pixel-copy Layla.

## Giai đoạn 1 — Nền tảng HLD bằng dữ liệu thật

- PostgreSQL repositories cho places, plans, users, preferences, events, consent, reminders và AI cost ledger.
- Redis rate-limit/cache/circuit state fail-closed; idempotency bền vững.
- Import OSM/Overpass có provenance; coverage gate theo category × district.
- OSRM matrix importer có profile/version/freshness metadata và origin legs.
- Open-Meteo forecast adapter.
- AI JSON adapter: provider switch, schema validation, timeout/retry/repair, cost accounting.
- Secure ownership, anonymous→account merge, expiry/cleanup and reminder worker.

## Giai đoạn 2 — Product workspace

- Chat liên tục với context/version history; natural-language extraction và tối đa ba field bổ sung.
- Split workspace: conversation, itinerary, interactive map; đồng bộ focus/selection.
- Day/city/transport/stay/activity hierarchy; ảnh, rating, opening state, provenance.
- Edit one stop, reorder, regenerate with constraints, undo/version compare.
- Share read-only, comments/feedback, trip history, notifications and post-trip feedback.
- Mobile in-trip mode, offline-safe itinerary, accessibility and observability.

## Giai đoạn 3 — Capability parity

- Multi-city/road-trip planning; flights, stays, transfers and activities via licensed provider APIs.
- Live price/availability snapshots with expiry and clear booking handoff.
- Currency/language/unit preferences; downloadable itinerary and collaboration.
- Human support workflow, escalation, itinerary review and booking assistance.
- Inspiration gallery, social proof, rich media and conversion-grade onboarding.
- Security, legal, performance, E2E and production readiness audit.

## Evidence gates

1. Every external datum includes provider, fetched-at and expiry/source URL where allowed.
2. No production path may silently fall back to memory, mock AI or demo routing.
3. Contract/integration tests run against PostgreSQL and Redis containers.
4. E2E covers create → refine → map → share → collaborate → reminder → booking handoff.
5. Parity matrix is checked against the current public Layla experience before release.
