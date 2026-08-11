---
title: 'Redesign Plan Result Header'
type: 'one-shot'
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Redesign Plan Result Header

## Intent

**Problem:** The result intro and trip summary area felt visually disconnected: the ready message was a large standalone card, while the trip title and facts below were loose and oversized.

**Approach:** Move the back-to-chat action into the ready card, style the ready state as a compact horizontal panel, and wrap the trip title/summary facts into one cohesive trip header card while preserving all existing plan-page behavior.

## Suggested Review Order

1. [`frontend/components/PlanView.tsx`](frontend/components/PlanView.tsx) — confirm only the result intro/trip header markup changed and existing actions remain.
2. [`frontend/app/globals.css`](frontend/app/globals.css) — confirm the new ready/header card styles, mobile stacking, and dark-mode compatibility.
