@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo محیط پایتون پروژه پیدا نشد.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" agent_graph.py
pause
