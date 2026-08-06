# Edge Case Hunter review request — localized settings

Invoke `bmad-review-edge-case-hunter` on this diff:

- `frontend/components/LocaleProvider.tsx`: added a typed settings contract with complete non-empty translations for 19 locales.
- `frontend/app/settings/page.tsx`: replaced hard-coded Vietnamese with locale keys; added strict preference response guards, localized safe errors, abortable load, synchronous mutation lock, localized destructive confirmation, and accessible busy/status states.
- `frontend/tests/i18n.test.mjs`: enforces every settings key for every supported locale.

Walk all branching paths and boundary conditions introduced or exposed by this diff. Report actionable edge cases with file/line and consequence. Do not edit files or use conversation history.
