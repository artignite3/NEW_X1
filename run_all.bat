@echo off
cd /d "%~dp0"
title NEW_X1 - Backend and ML Launcher
echo ======================================================================
echo    Starting NEW_X1: FastAPI + ML models + tunnel when available
echo    Website is already live at https://new-x1.pages.dev
echo ======================================================================

if exist "..\NEW_X1\env\Scripts\python.exe" (
    "..\NEW_X1\env\Scripts\python.exe" run_all.py %*
) else if exist "env\Scripts\python.exe" (
    "env\Scripts\python.exe" run_all.py %*
) else (
    python run_all.py %*
)

pause
