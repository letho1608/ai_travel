# Blind Hunter review request — localized login

Invoke the `bmad-review-adversarial-general` skill on this diff:

- `frontend/components/LocaleProvider.tsx`: added a typed login-copy contract and complete translations for all 19 supported locales; lookup now composes base and login catalogs.
- `frontend/app/login/page.tsx`: replaced Vietnamese chrome with locale keys, passes active locale to Google Identity Services, localizes safe OAuth failures, validates returned token, and blocks duplicate submissions with a synchronous ref.
- `frontend/tests/i18n.test.mjs`: verifies every supported locale contains the complete login contract.

Inspect current files directly. Review only this change for correctness, security, accessibility, race conditions, localization quality and maintainability. Do not edit files and do not rely on conversation history.
