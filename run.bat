@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  echo Please create .venv and install requirements first. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m study_desk %*
if errorlevel 1 pause
