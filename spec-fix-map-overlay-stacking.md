---
title: 'Fix Map Overlay Stacking'
type: 'one-shot'
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Intent

Prevent the itinerary map from painting above the sticky navigation or neighboring page content while the user scrolls.

# Change

- Raise the sticky navigation stacking layer above Leaflet map panes.
- Contain the map inside its own local stacking context with `position`, `z-index`, and `isolation`.
- Preserve the current itinerary/map layout and responsive behavior.
- Add a source-level regression assertion for the map/nav stacking contract.

# Review order

1. `frontend/app/globals.css` — verify the nav layer and map isolation rules.
2. `frontend/tests/i18n.test.mjs` — verify the regression contract covers the stacking fix.

# Verification

- `npm test` in `frontend`: passed, 24/24.
- `npx tsc --noEmit` in `frontend`: passed.
- `git diff --check`: clean, with existing LF-to-CRLF warnings only.
