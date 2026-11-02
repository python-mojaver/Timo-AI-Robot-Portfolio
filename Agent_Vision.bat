@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo محیط پایتون پروژه پیدا نشد. این فایل را داخل پروژه اصلی قرار دهید.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" agent_vision.py %*
pause
