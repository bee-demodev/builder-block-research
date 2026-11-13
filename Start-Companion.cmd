@echo off
rem Double-click to open the Trading Companion window.
rem Works from any folder: everything is resolved from where this file lives.
setlocal
set "REPO=%~dp0"
set "PYW=%REPO%.venv\Scripts\pythonw.exe"
set "PY=%REPO%.venv\Scripts\python.exe"

if exist "%PYW%" (
    rem pythonw has no console; "start" lets this window close straight away
    start "" /D "%REPO%" "%PYW%" -m companion.app
    exit /b 0
)

if exist "%PY%" (
    rem no pythonw in the venv: run python minimised instead
    start "Trading Companion" /MIN /D "%REPO%" "%PY%" -m companion.app
    exit /b 0
)

echo.
echo   Trading Companion could not start.
echo.
echo   The Python environment is missing. Expected to find:
echo     %PY%
echo.
echo   Create the .venv folder in %REPO% and install the project
echo   requirements into it, then double-click this file again.
echo.
pause
exit /b 1
