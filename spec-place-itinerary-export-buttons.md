---
title: 'Place Itinerary Export Buttons'
type: 'one-shot'
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Place Itinerary Export Buttons

## Intent

Problem: The PDF and calendar actions were in the itinerary page header, while the requested design places them inside the itinerary card action area.

Approach: Move the PDF and calendar links into the itinerary card, immediately above the save/share action row, and style them as compact two-column outline buttons with document/calendar icons. Use theme tokens and a 44px minimum target so the buttons remain readable in dark mode and usable on touch screens.

## Suggested Review Order

1. `frontend/components/PlanView.tsx` — confirm the header no longer contains export links and the itinerary card renders PDF/calendar before save/share.
2. `frontend/app/globals.css` — confirm the export buttons match the compact outline treatment, responsive grid, dark-mode-safe colors, and 44px touch target.
3. `frontend/tests/i18n.test.mjs` — confirm source contracts cover placement and styling.
