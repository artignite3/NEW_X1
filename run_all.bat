@echo off
title NEW_X1 - Universal Services Launcher
echo ======================================================================
echo    Starting NEW_X1: FastAPI + Product UI + Model UI
echo ======================================================================

if exist "env\Scripts\python.exe" (
    env\Scripts\python.exe run_all.py
) else (
    python run_all.py
)

pause
