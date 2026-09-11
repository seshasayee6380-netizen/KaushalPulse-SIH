@echo off
setlocal
cd /d %~dp0

echo =============================================
echo   KaushalPulse - Backend Starter
echo =============================================
echo.
echo [1/3] Stopping any old process using port 8010...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8010" ^| findstr "LISTENING"') do (
  echo     Killing PID %%P
  taskkill /PID %%P /F >nul 2>&1
)

echo [2/3] Preparing Python environment...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install -r backend\requirements.txt

echo [3/3] Starting KaushalPulse backend on http://127.0.0.1:8010
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
endlocal
