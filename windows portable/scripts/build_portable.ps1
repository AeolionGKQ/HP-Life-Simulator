[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pyprojectPath = Join-Path $projectRoot "pyproject.toml"
$frontendRoot = Join-Path $projectRoot "frontend"
$buildRoot = Join-Path $projectRoot "portable-build"
$distRoot = Join-Path $projectRoot "portable-dist"
$buildVenv = Join-Path $buildRoot "venv"
$buildPython = Join-Path $buildVenv "Scripts\python.exe"
$specPath = Join-Path $projectRoot "packaging\hp_simulator.spec"
$previousConfig = $env:HP_SIMULATOR_CONFIG

function Read-ProjectVersion {
    $line = Select-String -LiteralPath $pyprojectPath -Pattern '^version\s*=\s*"([^"]+)"$' | Select-Object -First 1
    if ($null -eq $line) {
        throw "Project version was not found in pyproject.toml."
    }
    return $line.Matches[0].Groups[1].Value
}

function Get-PlayerVersion([string]$Version) {
    $parts = $Version.Split(".")
    if ($parts.Length -ge 3 -and [int]$parts[2] -ne 0) {
        return "$($parts[0]).$($parts[1]).$($parts[2])"
    }
    return "$($parts[0]).$($parts[1])"
}

function Find-CommandPath([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        throw "Build environment is missing $Name."
    }
    return $command.Source
}

function Invoke-PythonModule([string[]]$Arguments) {
    & $buildPython @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python module failed: $($Arguments -join ' ')"
    }
}

function Write-VersionInfo([string]$Version) {
    $parts = $Version.Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = if ($parts.Length -ge 3) { [int]$parts[2] } else { 0 }
    $versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($major, $minor, $patch, 0),
    prodvers=($major, $minor, $patch, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '080404b0',
          [
            StringStruct('CompanyName', 'HP Simulator'),
            StringStruct('FileDescription', 'Hogwarts Life Simulator'),
            StringStruct('FileVersion', '$Version'),
            StringStruct('InternalName', 'HogwartsLifeSimulator'),
            StringStruct('OriginalFilename', 'HogwartsLifeSimulator.exe'),
            StringStruct('ProductName', 'Hogwarts Life Simulator'),
            StringStruct('ProductVersion', '$Version'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
    Set-Content -LiteralPath (Join-Path $projectRoot "packaging\version_info.txt") -Value $versionInfo -Encoding UTF8
}

$version = Read-ProjectVersion
$playerVersion = Get-PlayerVersion $version
$zipPath = Join-Path $projectRoot "HP-Life-Simulator-v$playerVersion-Windows-Portable.zip"
$pythonCommand = Find-CommandPath "python.exe"
$null = Find-CommandPath "node.exe"
$null = Find-CommandPath "npm.cmd"

if ((Test-Path -LiteralPath $zipPath) -and -not $Force) {
    throw "Target ZIP already exists. Use -Force to replace it."
}

Push-Location $projectRoot
try {
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
    if (Test-Path -LiteralPath $distRoot) {
        Remove-Item -LiteralPath $distRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $buildRoot, $distRoot | Out-Null

    & $pythonCommand -m venv $buildVenv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $buildPython)) {
        throw "Could not create the build virtual environment."
    }

    Invoke-PythonModule @("-m", "pip", "install", "--disable-pip-version-check", "-e", "$projectRoot`[dev`]")
    Invoke-PythonModule @("-m", "pip", "install", "-r", (Join-Path $projectRoot "packaging\requirements-build.txt"))
    Invoke-PythonModule @("-m", "scripts.create_windows_icon")
    Write-VersionInfo $version

    & npm.cmd --prefix $frontendRoot ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    & npm.cmd --prefix $frontendRoot run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }

    $env:HP_SIMULATOR_CONFIG = Join-Path $projectRoot "config\settings.example.toml"
    Invoke-PythonModule @("-m", "scripts.prepare_test_database")
    Invoke-PythonModule @("-m", "pytest")
    Invoke-PythonModule @("-m", "PyInstaller", "--clean", "--noconfirm", "--distpath", $distRoot, "--workpath", (Join-Path $buildRoot "pyinstaller"), $specPath)
    $env:HP_SIMULATOR_CONFIG = $previousConfig

    $builtFolder = Get-ChildItem -LiteralPath $distRoot -Directory | Select-Object -First 1
    if ($null -eq $builtFolder) {
        throw "PyInstaller did not produce a one-folder directory."
    }
    $stageRoot = Join-Path $buildRoot "stage"
    $packageRoot = Join-Path $stageRoot $builtFolder.Name
    New-Item -ItemType Directory -Path $packageRoot | Out-Null
    Copy-Item -Path (Join-Path $builtFolder.FullName "*") -Destination $packageRoot -Recurse
    Invoke-PythonModule @("-m", "scripts.create_player_guide", $packageRoot, $playerVersion)

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
    Invoke-PythonModule @("-m", "scripts.audit_portable_zip", $zipPath)

    Write-Host "Portable package created: $zipPath" -ForegroundColor Green
}
finally {
    $env:HP_SIMULATOR_CONFIG = $previousConfig
    Pop-Location
}
