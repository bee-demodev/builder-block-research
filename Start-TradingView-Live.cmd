@echo off
rem Starts TradingView Desktop with the live-data link the Trading Companion reads
rem (the debug port, 9222). Double-click it INSTEAD of the normal TradingView icon.
rem
rem It never closes or restarts TradingView. If TradingView is already open without
rem the link, it says so and stops: close TradingView yourself, then run this again.
rem
rem   Start-TradingView-Live.cmd           start TradingView with the link
rem   Start-TradingView-Live.cmd --check   only report what it finds; start nothing
rem
rem It always returns: TradingView is started detached (it does not inherit this
rem window or its output), every wait is bounded, and it only stops for a key press
rem when a person is at the keyboard (never when run by another program).
rem
rem For testing the start branch without touching TradingView, three environment
rem variables replace what it looks for: TVLIVE_EXE (the program to start),
rem TVLIVE_IMAGE (the process name that means "already running") and TVLIVE_PORT.
setlocal EnableExtensions
set "PORT=9222"
set "IMAGE=TradingView.exe"
if defined TVLIVE_PORT set "PORT=%TVLIVE_PORT%"
if defined TVLIVE_IMAGE set "IMAGE=%TVLIVE_IMAGE%"
set "CHECK_ONLY="
if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo.
call :port_answers
if not errorlevel 1 goto already_linked

tasklist /FI "IMAGENAME eq %IMAGE%" /NH 2>nul | find /I "%IMAGE%" >nul
if not errorlevel 1 goto running_without_link

rem --- find TradingView.exe: the usual installs, then the Microsoft Store one ---
set "TV_EXE="
if defined TVLIVE_EXE set "TV_EXE=%TVLIVE_EXE%"
if not defined TV_EXE if exist "%LOCALAPPDATA%\TradingView\TradingView.exe" set "TV_EXE=%LOCALAPPDATA%\TradingView\TradingView.exe"
if not defined TV_EXE if exist "%ProgramFiles%\TradingView\TradingView.exe" set "TV_EXE=%ProgramFiles%\TradingView\TradingView.exe"
if not defined TV_EXE if exist "%ProgramFiles(x86)%\TradingView\TradingView.exe" set "TV_EXE=%ProgramFiles(x86)%\TradingView\TradingView.exe"
if not defined TV_EXE call :find_store
if not defined TV_EXE call :find_on_path
if not defined TV_EXE goto not_found

echo   TradingView found:
echo     %TV_EXE%
if defined CHECK_ONLY (
    echo.
    echo   Check only: TradingView is not running and was not started.
    goto done_ok
)
echo.
echo   Starting TradingView with the live-data link on port %PORT% ...
rem Start-Process hands TradingView to the shell: it is not a child that shares this
rem window's output, so whoever ran this file is not left waiting for TradingView to exit.
set "TV_ARG=--remote-debugging-port=%PORT%"
powershell -NoProfile -Command "Start-Process -FilePath $env:TV_EXE -ArgumentList $env:TV_ARG"
if errorlevel 1 goto start_failed

set /a TRIES=0
:wait_for_port
set /a TRIES+=1
call :sleep 1
call :port_answers
if not errorlevel 1 goto started
if %TRIES% LSS 25 goto wait_for_port

echo.
echo   TradingView was started, but the live-data link is not answering yet.
echo   Give it a little longer. If the companion still says TradingView has no
echo   live-data link, close TradingView and run this file again.
echo.
call :hold
exit /b 1

:start_failed
echo.
echo   Windows would not start TradingView from:
echo     %TV_EXE%
echo   Start TradingView once from the Start menu to check it works, close it, then
echo   run this file again.
echo.
call :hold
exit /b 4

:started
echo.
echo   TradingView is running with the live-data link.
echo   Open the Trading Companion (Start-Companion.cmd) and choose
echo   Data: TradingView (live).
echo.
call :sleep 6
exit /b 0

:already_linked
echo   TradingView is already running with the live-data link (port %PORT%).
echo   Nothing to do: open the Trading Companion and choose Data: TradingView (live).
goto done_ok

:running_without_link
echo   TradingView is already open, but WITHOUT the live-data link.
echo.
echo   This launcher will not close it for you: you may be trading off it.
echo   When you are ready:
echo     1. Close TradingView yourself (all of its windows).
echo     2. Double-click this file again. It reopens TradingView with the link.
echo.
if not defined CHECK_ONLY call :hold
exit /b 2

:not_found
echo   TradingView Desktop was not found on this computer.
echo   Looked in:
echo     %LOCALAPPDATA%\TradingView
echo     %ProgramFiles%\TradingView
echo     the Microsoft Store apps (TradingView.Desktop)
echo.
echo   Install TradingView Desktop, or start it by hand with:
echo     TradingView.exe --remote-debugging-port=%PORT%
echo.
if not defined CHECK_ONLY call :hold
exit /b 3

:done_ok
echo.
if not defined CHECK_ONLY call :sleep 6
exit /b 0

rem --- helpers -----------------------------------------------------------------

:sleep
rem Waits %1 seconds. "timeout" refuses to run when input is redirected; ping does not care.
set /a PINGS=%~1+1
ping -n %PINGS% 127.0.0.1 >nul
exit /b 0

:hold
rem "Press any key" for a person; a short wait and no more when a program runs this file
rem (there a key press never comes, and "pause" would wait for ever).
powershell -NoProfile -Command "if ([Console]::IsInputRedirected) { exit 1 } else { exit 0 }" >nul 2>nul
if errorlevel 1 (
    call :sleep 2
    exit /b 0
)
pause
exit /b 0

:port_answers
rem errorlevel 0 when the debug port answers
where curl.exe >nul 2>nul
if errorlevel 1 goto port_by_powershell
curl.exe -s -m 2 -o nul "http://127.0.0.1:%PORT%/json/version"
exit /b %errorlevel%
:port_by_powershell
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/json/version'; exit 0 } catch { exit 1 }"
exit /b %errorlevel%

:find_store
rem The Microsoft Store install lives in a versioned folder under WindowsApps.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$p = Get-AppxPackage -Name 'TradingView.Desktop*' -ErrorAction SilentlyContinue | Sort-Object Version -Descending | Select-Object -First 1; if ($p) { $e = Join-Path $p.InstallLocation 'TradingView.exe'; if (Test-Path -LiteralPath $e) { Write-Output $e } }" 2^>nul`) do set "TV_EXE=%%i"
exit /b 0

:find_on_path
for /f "delims=" %%i in ('where TradingView.exe 2^>nul') do if not defined TV_EXE set "TV_EXE=%%i"
exit /b 0
