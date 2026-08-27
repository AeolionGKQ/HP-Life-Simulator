[CmdletBinding()]
param(
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$configPath = Join-Path $projectRoot "config\settings.local.toml"
$configExamplePath = Join-Path $projectRoot "config\settings.example.toml"
$pyprojectPath = Join-Path $projectRoot "pyproject.toml"
$packageLockPath = Join-Path $frontendRoot "package-lock.json"
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$backendUrl = "http://127.0.0.1:8000/api/health"
$frontendUrl = "http://127.0.0.1:5173"

function Stop-Launcher {
    param([string]$Message)

    Write-Host ""
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

function Get-FileHashValue {
    param([string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Test-HttpEndpoint {
    param([string]$Uri)

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -UseBasicParsing `
            -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)

    try {
        $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
        return $null -ne ($listeners | Where-Object { $_.Port -eq $Port } | Select-Object -First 1)
    } catch {
        return $false
    }
}

function Find-CompatiblePython {
    $candidates = @(
        [pscustomobject]@{ Name = "py.exe"; Prefix = @("-3.12") },
        [pscustomobject]@{ Name = "python.exe"; Prefix = @() },
        [pscustomobject]@{ Name = "python3.exe"; Prefix = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $command) {
            continue
        }

        try {
            $versionArgs = @($candidate.Prefix) + @(
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3])))"
            )
            $versionText = (& $command.Source $versionArgs 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($versionText)) {
                continue
            }
            $version = [version]$versionText.Trim()
            if ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 12)) {
                return [pscustomobject]@{
                    Command = $command.Source
                    Prefix = @($candidate.Prefix)
                    Version = $version
                }
            }
        } catch {
            continue
        }
    }

    return $null
}

Write-Host "==============================================" -ForegroundColor DarkCyan
Write-Host "  Hogwarts Life Simulator - Local Launcher" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor DarkCyan
Write-Host "[INFO] Project: $projectRoot"

foreach ($requiredPath in @(
    $configExamplePath,
    $pyprojectPath,
    $packageLockPath,
    (Join-Path $projectRoot "backend\app\main.py"),
    (Join-Path $frontendRoot "package.json")
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        Stop-Launcher "The project is incomplete. Missing: $requiredPath"
    }
}

if (-not (Test-Path -LiteralPath $configPath)) {
    Copy-Item -LiteralPath $configExamplePath -Destination $configPath
    Write-Host "[INFO] Created config\settings.local.toml from the example." -ForegroundColor Yellow
    Write-Host "[INFO] You can configure the model in the game, or edit this file manually." -ForegroundColor Yellow
}

$python = Find-CompatiblePython
if ($null -eq $python) {
    Stop-Launcher "Python 3.12 or newer was not found. Install it, enable PATH, and run this launcher again."
}
Write-Host "[OK] Python $($python.Version)"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[INFO] Creating the project-local Python environment..."
    $venvArgs = @($python.Prefix) + @("-m", "venv", $venvRoot)
    & $python.Command $venvArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Stop-Launcher "Failed to create .venv. Check the Python installation and folder permissions."
    }
}

try {
    $venvVersionText = (& $venvPython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" | Select-Object -Last 1)
    $venvVersion = [version]$venvVersionText.Trim()
} catch {
    Stop-Launcher "The existing .venv is damaged. Delete the .venv folder and run the launcher again."
}
if ($venvVersion.Major -lt 3 -or ($venvVersion.Major -eq 3 -and $venvVersion.Minor -lt 12)) {
    Stop-Launcher "The existing .venv uses Python $venvVersion. Delete .venv and recreate it with Python 3.12 or newer."
}

$pythonMarkerPath = Join-Path $venvRoot ".hp-simulator-pyproject.sha256"
$pyprojectHash = Get-FileHashValue $pyprojectPath
$savedPyprojectHash = if (Test-Path -LiteralPath $pythonMarkerPath) {
    (Get-Content -LiteralPath $pythonMarkerPath -Raw).Trim()
} else {
    ""
}

$backendImportsWork = $false
if ($savedPyprojectHash -eq $pyprojectHash) {
    & $venvPython -c "import fastapi, httpx, pydantic, sqlalchemy, tomli_w, uvicorn; import backend.app.main" 2>$null
    $backendImportsWork = $LASTEXITCODE -eq 0
}

if (-not $backendImportsWork) {
    Write-Host "[INFO] Installing backend dependencies. The first run may take a few minutes..."
    & $venvPython -m pip install --disable-pip-version-check -e $projectRoot
    if ($LASTEXITCODE -ne 0) {
        Stop-Launcher "Backend dependency installation failed. Check the network and Python installation."
    }
    Set-Content -LiteralPath $pythonMarkerPath -Value $pyprojectHash -Encoding ASCII
}
Write-Host "[OK] Backend dependencies"

$nodeCommand = Get-Command "node.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $nodeCommand -or $null -eq $npmCommand) {
    Stop-Launcher "Node.js and npm were not found. Install the current Node.js LTS release, then run this launcher again."
}

try {
    $nodeVersionText = (& $nodeCommand.Source --version).Trim().TrimStart("v")
    $nodeVersion = [version]$nodeVersionText
} catch {
    Stop-Launcher "The Node.js version could not be detected. Reinstall the current Node.js LTS release."
}
if ($nodeVersion.Major -lt 18) {
    Stop-Launcher "Node.js $nodeVersion is too old. Install Node.js 18 or a newer LTS release."
}
Write-Host "[OK] Node.js $nodeVersion"

$nodeModulesPath = Join-Path $frontendRoot "node_modules"
$nodeMarkerPath = Join-Path $nodeModulesPath ".hp-simulator-package-lock.sha256"
$packageLockHash = Get-FileHashValue $packageLockPath
$savedPackageLockHash = if (Test-Path -LiteralPath $nodeMarkerPath) {
    (Get-Content -LiteralPath $nodeMarkerPath -Raw).Trim()
} else {
    ""
}

$frontendDependenciesWork = $false
if (Test-Path -LiteralPath $nodeModulesPath) {
    if ($savedPackageLockHash -eq $packageLockHash) {
        & $npmCommand.Source --prefix $frontendRoot ls --depth=0 1>$null 2>$null
        $frontendDependenciesWork = $LASTEXITCODE -eq 0
    } elseif (-not (Test-Path -LiteralPath $nodeMarkerPath)) {
        & $npmCommand.Source --prefix $frontendRoot ls --depth=0 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            Set-Content -LiteralPath $nodeMarkerPath -Value $packageLockHash -Encoding ASCII
            $frontendDependenciesWork = $true
        }
    }
}

if (-not $frontendDependenciesWork) {
    Write-Host "[INFO] Installing frontend dependencies. The first run may take a few minutes..."
    & $npmCommand.Source --prefix $frontendRoot ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {
        Stop-Launcher "Frontend dependency installation failed. Check the network and Node.js installation."
    }
    Set-Content -LiteralPath $nodeMarkerPath -Value $packageLockHash -Encoding ASCII
}
Write-Host "[OK] Frontend dependencies"

$backendReady = Test-HttpEndpoint $backendUrl
$frontendReady = Test-HttpEndpoint $frontendUrl

if (-not $backendReady -and (Test-PortListening 8000)) {
    Stop-Launcher "Port 8000 is already used by another program. Close that program and try again."
}
if (-not $frontendReady -and (Test-PortListening 5173)) {
    Stop-Launcher "Port 5173 is already used by another program. Close that program and try again."
}

if ($ValidateOnly) {
    Write-Host "[OK] Launcher validation completed. No service was started." -ForegroundColor Green
    exit 0
}

if (-not $backendReady) {
    Write-Host "[INFO] Starting the FastAPI backend..."
    Start-Process `
        -FilePath $venvPython `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) `
        -WorkingDirectory $projectRoot | Out-Null
} else {
    Write-Host "[INFO] The backend is already running."
}

if (-not $frontendReady) {
    Write-Host "[INFO] Starting the React frontend..."
    Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--strictPort") `
        -WorkingDirectory $frontendRoot | Out-Null
} else {
    Write-Host "[INFO] The frontend is already running."
}

Write-Host "[INFO] Waiting for both services, then opening the browser..."
& (Join-Path $PSScriptRoot "wait_and_open.ps1")
exit $LASTEXITCODE
