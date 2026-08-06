# Edge Case Hunter review request — localized login

Invoke the `bmad-review-edge-case-hunter` skill on this diff:

- `frontend/components/LocaleProvider.tsx`: added a typed login-copy contract and complete translations for all 19 supported locales; lookup now composes base and login catalogs.
- `frontend/app/login/page.tsx`: replaced Vietnamese chrome with locale keys, passes active locale to Google Identity Services, localizes safe OAuth failures, validates returned token, and blocks duplicate submissions with a synchronous ref.
- `frontend/tests/i18n.test.mjs`: verifies every supported locale contains the complete login contract.

Walk every branching path and boundary condition introduced or exposed by this diff. Report only actionable unhandled edge cases with file/line and consequence. Do not edit files and do not rely on conversation history.
