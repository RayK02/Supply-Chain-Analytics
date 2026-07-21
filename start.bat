@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Die Anwendung ist noch nicht eingerichtet. setup.ps1 wird gestartet.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" || exit /b 1
)
start "Aussenlager Tracker" /min ".venv\Scripts\python.exe" -m waitress --listen=127.0.0.1:5050 run:app
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5050"
echo Aussenlager Tracker laeuft unter http://127.0.0.1:5050

