---
title: 'Simplify Itinerary Export Actions'
type: 'one-shot'
created: '2026-08-11'
status: 'done'
route: 'one-shot'
---

# Simplify Itinerary Export Actions

## Intent

Problem: The itinerary header action area was crowded with share, JSON, comments, version, and regenerate controls when the user only wanted export actions there.

Approach: Keep only the PDF download and calendar links in a compact export group at the itinerary header, with responsive styling so the two links remain easy to tap on mobile. Existing itinerary card actions and backend behavior are left untouched.

## Suggested Review Order

1. `frontend/components/PlanView.tsx` — confirm the trip header renders only `downloadPdf` and `addCalendar`.
2. `frontend/app/globals.css` — confirm `.export-actions` aligns the links cleanly on desktop and lets them flex on mobile.
