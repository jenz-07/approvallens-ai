@echo off
setlocal
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Start Docker Desktop with Linux containers, then run this file again.
  pause
  exit /b 1
)
if not exist .env copy .env.example .env >nul
echo Building and starting ApprovalLens AI. The first launch downloads dependencies.
docker compose up --build -d
if errorlevel 1 goto failed
docker compose exec -T api python -m app.seed
if errorlevel 1 goto failed
echo.
echo ApprovalLens AI: http://localhost:3000
echo Accounts: applicant@demo.local / reviewer@demo.local / admin@demo.local
echo Demo password: DemoOnly!2026
start "" "http://localhost:3000"
pause
exit /b 0
:failed
echo Startup did not complete. See the error above. Your data has not been deleted.
pause
exit /b 1
