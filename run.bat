@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"

set "PYTHON_EXE="
if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
if not defined PYTHON_EXE where python >nul 2>nul && set "PYTHON_EXE=python"
if not defined PYTHON_EXE if exist "C:\Users\1212a\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_EXE=C:\Users\1212a\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

set "NODE_EXE="
where node >nul 2>nul && set "NODE_EXE=node"
if not defined NODE_EXE if exist "C:\Users\1212a\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" set "NODE_EXE=C:\Users\1212a\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if not defined PYTHON_EXE (
  echo [ERROR] Khong tim thay Python 3.10+.
  echo Hay cai Python, sau do chay lai run.bat.
  pause
  exit /b 1
)

if not defined NODE_EXE (
  echo [ERROR] Khong tim thay Node.js 18+.
  echo Hay cai Node.js, sau do chay lai run.bat.
  pause
  exit /b 1
)

if not exist "%PROJECT_ROOT%\backend\app\main.py" (
  echo [ERROR] Khong tim thay backend\app\main.py.
  pause
  exit /b 1
)

if not exist "%PROJECT_ROOT%\frontend\node_modules\next\dist\bin\next" (
  echo [ERROR] Frontend chua co dependency.
  echo Chay "cd frontend" va "npm install" hoac "pnpm install" truoc.
  pause
  exit /b 1
)

if exist "%PROJECT_ROOT%\.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%PROJECT_ROOT%\.env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
) else (
  echo [WARN] Chua co file .env. Dang dung cau hinh local/mac dinh.
  echo        De bat AI that: copy .env.example thanh .env, dat AI_MODE=groq va API_KEY_GROQ.
)

if /I "%AI_MODE%"=="groq" goto AI_MODE_GROQ
if /I "%AI_MODE%"=="deepseek" goto AI_MODE_DEEPSEEK
echo [WARN] AI dang chay mock. Tinh nang AI se dung deterministic fallback.
goto AI_MODE_DONE

:AI_MODE_GROQ
if "%API_KEY_GROQ%"=="" (
  echo [WARN] AI_MODE=groq nhung API_KEY_GROQ dang trong. Backend se loi khi goi AI.
) else (
  echo AI live mode: groq (%TEN_MODEL_GROQ%)
)
goto AI_MODE_DONE

:AI_MODE_DEEPSEEK
if "%API_KEY_DEEPSEEK%"=="" (
  echo [WARN] AI_MODE=deepseek nhung API_KEY_DEEPSEEK dang trong. Backend se loi khi goi AI.
) else (
  echo AI live mode: deepseek (%TEN_MODEL_DEEPSEEK%)
)

:AI_MODE_DONE
if "%PLACES_DATA_FILE%"=="" set "PLACES_DATA_FILE=vietnam_places.json"

where docker >nul 2>nul
if errorlevel 1 goto DOCKER_MISSING
docker compose up -d
if errorlevel 1 goto DOCKER_FAILED

set "URL_CSDL_POSTGRES=postgresql://postgres:postgres@localhost:5432/minhdidauthe"
set "URL_CSDL_REDIS=redis://localhost:6379/0"
"%PYTHON_EXE%" "%PROJECT_ROOT%\backend\scripts\ensure_local_data.py"
if errorlevel 1 goto DATA_FAILED

set "BACKEND_PORT=8000"
:CHECK_BACKEND_PORT
curl.exe -fsS "http://localhost:%BACKEND_PORT%/health" 2>nul | findstr /C:"postgresql" | findstr /C:"redis" | findstr /C:"%AI_MODE%" | findstr /C:"%PLACES_DATA_FILE%" >nul
if not errorlevel 1 goto BACKEND_REUSED
netstat -ano | findstr /R /C:":%BACKEND_PORT% .*LISTENING" >nul
if errorlevel 1 goto BACKEND_PORT_READY
set /a BACKEND_PORT+=1
if %BACKEND_PORT% LEQ 8010 goto CHECK_BACKEND_PORT
echo [ERROR] Tat ca cong backend 8000-8010 dang duoc su dung.
pause
exit /b 1

:BACKEND_REUSED
echo Reusing verified Backend: http://localhost:%BACKEND_PORT%
goto BACKEND_STARTED

:BACKEND_PORT_READY
echo Starting durable Backend: http://localhost:%BACKEND_PORT%
if defined RUN_BAT_CHECK_ONLY goto BACKEND_STARTED
start "Minh Di Dau The - Backend" /D "%PROJECT_ROOT%\backend" cmd /k "set "USE_DURABLE_LOCAL=true"&& set "PLACES_DATA_FILE=%PLACES_DATA_FILE%"&& set "URL_CSDL_POSTGRES=%URL_CSDL_POSTGRES%"&& set "URL_CSDL_REDIS=%URL_CSDL_REDIS%"&& set "AI_MODE=%AI_MODE%"&& set "API_KEY_GROQ=%API_KEY_GROQ%"&& set "TEN_MODEL_GROQ=%TEN_MODEL_GROQ%"&& set "API_KEY_DEEPSEEK=%API_KEY_DEEPSEEK%"&& set "TEN_MODEL_DEEPSEEK=%TEN_MODEL_DEEPSEEK%"&& set "AI_BASE_URL=%AI_BASE_URL%"&& set "GOOGLE_MAPS_API_KEY=%GOOGLE_MAPS_API_KEY%"&& set "GOOGLE_PLACES_TEXT_SEARCH_DAILY_CAP=%GOOGLE_PLACES_TEXT_SEARCH_DAILY_CAP%"&& set "GOOGLE_PLACES_TEXT_SEARCH_MONTHLY_CAP=%GOOGLE_PLACES_TEXT_SEARCH_MONTHLY_CAP%"&& set "GOOGLE_PLACES_PHOTO_DAILY_CAP=%GOOGLE_PLACES_PHOTO_DAILY_CAP%"&& set "GOOGLE_PLACES_PHOTO_MONTHLY_CAP=%GOOGLE_PLACES_PHOTO_MONTHLY_CAP%"&& set "GOOGLE_PLACES_HOURS_DAILY_CAP=%GOOGLE_PLACES_HOURS_DAILY_CAP%"&& set "GOOGLE_PLACES_HOURS_MONTHLY_CAP=%GOOGLE_PLACES_HOURS_MONTHLY_CAP%"&& set "GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP=%GOOGLE_PLACES_RUNTIME_PER_PLAN_CAP%"&& set "GOOGLE_PLACES_RUNTIME_PHOTOS=%GOOGLE_PLACES_RUNTIME_PHOTOS%"&& set "GOOGLE_PLACES_RUNTIME_HOURS=%GOOGLE_PLACES_RUNTIME_HOURS%"&& "%PYTHON_EXE%" -m uvicorn app.main:app --reload --port %BACKEND_PORT%"

:BACKEND_STARTED
set "FRONTEND_PORT=3000"
:CHECK_FRONTEND_PORT
netstat -ano | findstr /R /C:":%FRONTEND_PORT% .*LISTENING" >nul
if errorlevel 1 goto FRONTEND_PORT_READY
set /a FRONTEND_PORT+=1
if %FRONTEND_PORT% LEQ 3010 goto CHECK_FRONTEND_PORT
echo [ERROR] Tat ca cong 3000-3010 dang duoc su dung.
echo Hay dong mot server frontend cu va chay lai run.bat.
pause
exit /b 1

:FRONTEND_PORT_READY
if defined RUN_BAT_CHECK_ONLY goto CHECK_ONLY_DONE
echo Starting Frontend: http://localhost:%FRONTEND_PORT%
start "Minh Di Dau The - Frontend" /D "%PROJECT_ROOT%\frontend" cmd /k "set "NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT%"&& set "NEXT_PUBLIC_BASE_URL=http://localhost:%FRONTEND_PORT%"&& "%NODE_EXE%" node_modules\next\dist\bin\next dev -p %FRONTEND_PORT%"

echo.
echo Da mo Backend va Frontend trong hai cua so rieng.
echo Frontend URL: http://localhost:%FRONTEND_PORT%
echo Dong hai cua so do de dung ung dung.
timeout /t 3 >nul

endlocal
exit /b 0

:CHECK_ONLY_DONE
echo Launcher check OK. Backend port %BACKEND_PORT%, frontend port %FRONTEND_PORT%.
endlocal
exit /b 0

:DOCKER_MISSING
echo [ERROR] Khong tim thay Docker. Can Docker Desktop de chay PostgreSQL va Redis that.
pause
exit /b 1

:DOCKER_FAILED
echo [ERROR] Khong khoi dong duoc PostgreSQL/Redis. Hay mo Docker Desktop va thu lai.
pause
exit /b 1

:DATA_FAILED
echo [ERROR] Khong the tao schema hoac nap du lieu OSM/OSRM da kiem chung.
pause
exit /b 1
