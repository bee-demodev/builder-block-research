@echo off
rem Double-click to open the Trading Companion app (the core and its UI in one window).
rem Works from any folder: everything is resolved from where this file lives.
rem A second double-click brings the open window to the front instead of starting another.
setlocal
set "REPO=%~dp0"
set "PYW=%REPO%.venv\Scripts\pythonw.exe"
set "PY=%REPO%.venv\Scripts\python.exe"

if exist "%PYW%" (
    rem pythonw has no console; "start" lets this window close straight away
    start "" /D "%REPO%" "%PYW%" -m companion.desktop
    exit /b 0
)

if exist "%PY%" (
    rem no pythonw in the venv: run python minimised instead
    start "Trading Companion" /MIN /D "%REPO%" "%PY%" -m companion.desktop
    exit /b 0
)

echo.
echo   Trading Companion could not start.
echo.
echo   The Python environment is missing. Expected to find:
echo     %PY%
echo.
echo   Create the .venv folder in %REPO% and install the companion
echo   requirements into it (companion\requirements.txt), then double-click
echo   this file again.
echo.
pause
exit /b 1
