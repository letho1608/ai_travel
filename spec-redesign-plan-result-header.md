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

**Approach:** Keep the back-to-chat action in its own top row, render no app name on the right, style the “AI finished / suggested itinerary” block as a white rounded card beneath it, and preserve the plan title/summary facts in a compact card below.

## Suggested Review Order

1. [`frontend/components/PlanView.tsx`](frontend/components/PlanView.tsx) — confirm the result topbar and ready card match the mockup without a right-side app label while retaining plan-specific summary content.
2. [`frontend/app/globals.css`](frontend/app/globals.css) — confirm the back pill, ready card, compact summary card, mobile spacing, and dark-mode compatibility.
