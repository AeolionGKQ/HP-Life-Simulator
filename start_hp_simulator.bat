@echo off
setlocal

rem Use the directory of this batch file as the project root.
set "PROJECT_ROOT=%~dp0"
pushd "%PROJECT_ROOT%"

title HP Simulator Launcher

if not exist "config\settings.local.toml" (
    echo [ERROR] Missing config\settings.local.toml
    echo Create it from config\settings.example.toml before starting the game.
    pause
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found. Install Python 3.12 or newer.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Install Node.js.
    pause
    exit /b 1
)

python -m pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing backend dependencies. This may take a while on the first run...
    python -m pip install -e ".[dev]"
    if errorlevel 1 (
        echo [ERROR] Backend dependency installation failed.
        pause
        exit /b 1
    )
)

if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies. This may take a while on the first run...
    call npm --prefix "frontend" install
    if errorlevel 1 (
        echo [ERROR] Frontend dependency installation failed.
        pause
        exit /b 1
    )
)

echo [INFO] Starting the FastAPI backend...
start "HP Simulator - Backend" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -Command ^
    "Set-Location -LiteralPath '%PROJECT_ROOT%'; python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"

echo [INFO] Starting the React frontend...
start "HP Simulator - Frontend" powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -Command ^
    "Set-Location -LiteralPath '%PROJECT_ROOT%frontend'; npm run dev"

echo [INFO] Waiting for the frontend and opening the browser...
start "HP Simulator - Browser" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\wait_and_open.ps1"

popd
exit /b 0

