@echo off
setlocal EnableExtensions DisableDelayedExpansion
title HP Simulator Launcher

set "LAUNCHER_SCRIPT=%~dp0scripts\start_hp_simulator.ps1"

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Windows PowerShell was not found.
    echo Use the manual startup instructions in README.md instead.
    pause
    exit /b 1
)

if not exist "%LAUNCHER_SCRIPT%" (
    echo [ERROR] Missing scripts\start_hp_simulator.ps1
    echo Download or extract the complete project, then try again.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_SCRIPT%"
set "LAUNCH_RESULT=%ERRORLEVEL%"

if not "%LAUNCH_RESULT%"=="0" (
    echo.
    echo The game could not be started. Review the message above.
    echo You can also use the manual startup instructions in README.md.
    pause
)

exit /b %LAUNCH_RESULT%
