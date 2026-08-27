$ErrorActionPreference = "SilentlyContinue"

$frontendUrl = "http://127.0.0.1:5173"
$healthUrl = "http://127.0.0.1:8000/api/health"
$maxAttempts = 90
$frontendReady = $false
$backendReady = $false

function Test-HttpEndpoint {
    param([string]$Uri)

    try {
        $response = Invoke-WebRequest `
            -Uri $Uri `
            -UseBasicParsing `
            -TimeoutSec 1
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $frontendReady = Test-HttpEndpoint $frontendUrl
    $backendReady = Test-HttpEndpoint $healthUrl
    if ($frontendReady -and $backendReady) {
        Start-Process $frontendUrl
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "[ERROR] The game did not become ready in time." -ForegroundColor Red
Write-Host "Backend ready: $backendReady"
Write-Host "Frontend ready: $frontendReady"
Write-Host "Review the backend and frontend windows for the detailed error."
exit 1
