@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto fail
)
if not exist ".venv\installed-v04" (
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto fail
    type nul > .venv\installed-v04
)
.venv\Scripts\python.exe start.py
if errorlevel 1 goto fail
exit /b 0
:fail
 echo.
 echo Startup stopped. Read the message above, correct the setup and try again.
 pause
 exit /b 1
