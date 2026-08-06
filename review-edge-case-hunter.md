# Edge Case Hunter review request

Invoke the `bmad-review-edge-case-hunter` skill on this diff:

- `frontend/components/LocaleProvider.tsx`: expanded the translation contract from five navigation keys to include history/loading/empty-state/notification/read-action copy for all 19 supported locales; added placeholder interpolation; stabilized `t` with `useCallback`.
- `frontend/app/history/page.tsx`: replaced hard-coded Vietnamese history and notification chrome with locale keys; localized loading and empty states; refetches after locale changes.
- `frontend/package.json`: changed the Node test target from the shell-dependent `tests/*.test.mjs` glob to the cross-platform `tests` directory.
- `PARITY_MATRIX.md`: updated only the verified localization evidence and retained the overall status as partial.

Walk every branching path and boundary condition in the current files. Report only unhandled edge cases introduced or exposed by this diff. Do not rely on prior conversation.
