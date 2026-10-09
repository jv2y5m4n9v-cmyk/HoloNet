@echo off
if not exist "%~dp0venv\Scripts\pythonw.exe" (
  echo Python virtual environment not found. Run setup.ps1 first.
  pause
  exit /b 1
)
start "HoloNet" "%~dp0venv\Scripts\pythonw.exe" "%~dp0app.py" %*
