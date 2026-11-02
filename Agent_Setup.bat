@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" setup_agent.py
) else (
    py -3 setup_agent.py
)
pause
