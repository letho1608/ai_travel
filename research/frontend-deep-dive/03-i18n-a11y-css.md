# Frontend Deep Dive: I18N, Accessibility & CSS

## 1. I18N (Internationalization) Audit

**Target Files:**
- `frontend/lib/i18n-core.ts`
- `frontend/components/LocaleProvider.tsx`
- `frontend/components/Planner.tsx`

### Findings

- **Locale Count:** 19 locales supported (`vi`, `en`, `ar`, `bg`, `de`, `es`, `fr`, `he`, `hi`, `it`, `ja`, `nl`, `pl`, `pt`, `ru`, `tr`, `zh`, `ko`, `th`).
- **Translation Keys (Planner):** 28 keys defined in `plannerTranslationKeys` within `i18n-core.ts`.
- **`LocaleProvider.tsx` Coverage:** All 19 locales are fully populated with all 28 `plannerTranslationKeys`. The expected `chatWelcome`, `chatPlaceholder`, and `sendChat` are present across all languages.
- **RTL Support:** Implemented via `document.documentElement.dir=["ar","he"].includes(next)?"rtl":"ltr"`. **Note:** Hardcoded RTL logic in JS might cause a flash of LTR before hydration.

## 2. Accessibility (A11y) Audit

**Target Files:**
- `frontend/components/Planner.tsx`
- `frontend/app/globals.css`

### Findings

- **html lang attribute:** Dynamically updated in `LocaleProvider.tsx` (`document.documentElement.lang=next;`), which is good for screen readers.
- **`aria-label` & roles:**
  - `Planner.tsx`: The input field for chat has `aria-label={t("chatPlaceholder")}`, which is redundant with the `placeholder` attribute but acceptable. The submit button has `aria-label={t("sendChat")}`.
  - The status message uses `role="status" aria-live="polite"`. The error message uses `role="alert"`. This is **Excellent** for dynamic updates.
- **Contrast & Focus:**
  - `globals.css`: Focus outlines are mostly default browser styles, except for `.slot-select:focus-visible{outline:3px solid #54a692;outline-offset:2px}`.
  - **Medium Issue:** The contrast ratio of the placeholder text in the dark mode input (`#0f1815` background) might be too low. Needs checking.
- **Semantic Markup:**
  - `Planner.tsx`: Uses `<form>`, `<label>`, `<input>`, `<button>`. **Good**.
- **Keyboard Navigation:**
  - The "quick actions" chips are `<button type="button">`, so they are keyboard accessible.
- **Alt Text:** N/A for `Planner.tsx` as it lacks images.

## 3. Styling & Responsive Audit

**Target Files:**
- `frontend/app/globals.css`

### Findings

- **Responsive Design (`@media (max-width: 760px)`)**:
  - `globals.css` includes `@media(max-width:760px)` handling `.shell` padding, `.nav`, `.workspace` layout, `.trip-header`, and `.itinerary-panel`. The layout collapses to a single column effectively.
- **Dark Mode (`@media (prefers-color-scheme: dark)`)**:
  - Comprehensive color variables update (`--ink`, `--muted`, `--paper`, `--brand`, `--line`).
  - `.planner` background and border adjust correctly.
- **Specifics (`.chat-welcome`, flex-wrap header)**:
  - `.chat-welcome`: Uses `display:flex;gap:10px;align-items:center;margin-bottom:14px`.
  - Header (`.trip-header`): Uses `display:flex;justify-content:space-between;gap:24px;align-items:flex-end;`. In the `<760px` query, it changes to `align-items:flex-start;flex-direction:column;`. **Good**.

## Summary

The frontend codebase demonstrates a robust internationalization setup, supporting 19 locales with complete key coverage for the planner component. The accessibility implementation is commendable, featuring appropriate ARIA roles (`status`, `alert`) for dynamic state changes and maintaining semantic HTML. The CSS styling is clean, with responsive breakpoints correctly converting complex layouts to single columns for mobile, and a comprehensive dark mode implementation based on system preferences. The RTL logic in `LocaleProvider` is noted as potentially causing a brief flash before hydration. Overall, the foundational aspects are solid.

**Confidence Score: 9/10**
