# AI_Travel1 goal handoff

Current goal:

> Các nút tương tác trên web chưa hoạt động, còn thiếu dữ liệu, AI, thiếu khả năng tương tác, thiếu admin page riêng của admin để quản lý hệ thống.

## Current verified state

- Backend and frontend can be launched with `run.bat`.
- `run.bat` now loads `.env` from the project root and forwards AI environment variables to the backend.
- `.env` exists and is ready for local configuration.
- `.gitignore` excludes `.env` and common local build/dependency folders so real API keys are not committed by accident.
- Admin page exists at `http://localhost:3000/admin`.
- Admin token for local support/demo: `local-support-demo`.
- Admin APIs include dashboard, provider diagnostics, AI quality, data quality, catalog search/export, plans, users, AI usage, events, and maintenance cleanup.
- Verified catalog data is present: 3508 OpenStreetMap places.
- Catalog quality endpoint: `GET http://localhost:8000/api/admin/catalog/quality`.
- Latest verification before this handoff:
  - Backend tests: `98 passed, 5 skipped`.
  - Frontend node tests: `19 passed`.
  - TypeScript: pass.
  - ESLint: pass.
  - Next production build: pass.
  - Runtime smoke: backend health OK, `/admin` returns 200.

## Remaining blocker before marking goal complete

AI live has not been verified because the local `.env` still has:

```env
AI_MODE=groq
API_KEY_GROQ=
```

Runtime therefore reports:

```json
{"ai_mode":"groq"} sau khi backend duoc restart voi key hop le
```

## To finish AI live verification

1. Open `.env`.
2. Set:

```env
AI_MODE=groq
API_KEY_GROQ=<real Groq key>
```

3. Stop old backend/frontend windows.
4. Run:

```bat
run.bat
```

5. Verify:

```powershell
cd D:\AILearning\AI_Travel1
.\backend\.venv\Scripts\python.exe backend\scripts\check_ai_env.py
.\backend\.venv\Scripts\python.exe backend\scripts\final_smoke.py
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/api/admin/ai-quality -Headers @{"X-Admin-Token"="local-support-demo"}
```

Expected:

- `health.ai_mode` is `groq`.
- `ai-quality.live_provider_ready` is `true`.
- A new generated plan should not be counted as deterministic mock output.

## Useful final smoke set

```powershell
cd D:\AILearning\AI_Travel1\backend
.\.venv\Scripts\python.exe -m pytest -q

cd D:\AILearning\AI_Travel1\frontend
node --test tests
.\node_modules\.bin\tsc.CMD --noEmit
.\node_modules\.bin\eslint.CMD .
.\node_modules\.bin\next.CMD build
```

## Do not mark the persistent goal complete until

- Admin page and admin APIs are verified in runtime.
- Catalog/data quality is verified in runtime.
- Main user interactions still pass smoke checks.
- AI live is configured and verified, or the user explicitly accepts mock AI as sufficient.
