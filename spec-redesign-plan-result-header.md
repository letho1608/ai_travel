---
title: 'Redesign Plan Result Header'
type: 'one-shot'
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Redesign Plan Result Header

## Intent

**Problem:** The generated-result intro needed to match the approved mockup: a small back-to-chat pill above a clean “AI finished” suggestion card.

**Approach:** Keep the back-to-chat action in its own top row, render no app name on the right, style the “AI finished / suggested itinerary” block as a white rounded card beneath it, and remove the extra trip-summary card from this top area.

## Suggested Review Order

1. [`frontend/components/PlanView.tsx`](frontend/components/PlanView.tsx) — confirm the result topbar and ready card match the mockup without a right-side app label or extra trip-summary card.
2. [`frontend/app/globals.css`](frontend/app/globals.css) — confirm the back pill, ready card, mobile spacing, and dark-mode compatibility.
