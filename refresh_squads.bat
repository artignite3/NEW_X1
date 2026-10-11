@echo off
cd /d "%~dp0"
if not exist "..\NEW_X1\env\Scripts\python.exe" (
    echo Artifact checkout not found at ..\NEW_X1
    exit /b 1
)
set "NEW_X1_DATA_ROOT=%~dp0..\NEW_X1\data"
"..\NEW_X1\env\Scripts\python.exe" -c "from dotenv import load_dotenv; load_dotenv(r'%~dp0..\NEW_X1\.env'); from data.future_matches.squad_fetcher import main; main()" %*
