$ErrorActionPreference = "SilentlyContinue"

$frontendUrl = "http://127.0.0.1:5173"
$healthUrl = "http://127.0.0.1:8000/api/health"
$maxAttempts = 60
$ready = $false

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
        $frontendResponse = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 2
        if ($frontendResponse.StatusCode -ge 200 -and $frontendResponse.StatusCode -lt 500) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if ($ready) {
    Start-Process $frontendUrl
} else {
    Write-Host "The frontend did not respond in time. Check the frontend terminal." -ForegroundColor Yellow
    try {
        Start-Process $healthUrl
    } catch {
        Start-Process $frontendUrl
    }
}

