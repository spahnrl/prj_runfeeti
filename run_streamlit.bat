@echo off
setlocal
cd /d "%~dp0"

set "APP=%~dp0streamlit_app.py"
set "PY="

if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo Starting RunFeeti (Streamlit)...
echo Project: %~dp0
echo.

"%PY%" -m streamlit run "%APP%"

if errorlevel 1 (
  echo.
  echo Streamlit exited with an error. Press any key to close.
  pause >nul
)

endlocal
