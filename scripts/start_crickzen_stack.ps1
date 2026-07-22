param(
    [string]$FrontendRoot = 'C:\Users\ADMINS\Documents\projects\victoryline-monorepo',
    [switch]$BuildFrontend,
    [switch]$CleanStart
)

$ErrorActionPreference = 'Stop'
$ModelRoot = Split-Path -Parent $PSScriptRoot
$DashboardRoot = Join-Path $ModelRoot 'dashboard'
$Python = Join-Path $DashboardRoot '.venv313\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = Join-Path $DashboardRoot '.venv\Scripts\python.exe'
}
$env:PROJECT_ROOT = $ModelRoot
$env:PYTHONPATH = "$ModelRoot\src;$DashboardRoot"

function Stop-CricketPredictionProcesses {
    $modelRootPattern = [regex]::Escape($ModelRoot)
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and (
            ($_.CommandLine -match $modelRootPattern -and $_.CommandLine -match 'crex_live_predictor') -or
            ($_.CommandLine -match [regex]::Escape($DashboardRoot) -and $_.CommandLine -match 'uvicorn app\.main:app')
        )
    }
    foreach ($process in $processes) {
        if ($process.ProcessId -ne $PID) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 1
}

function Wait-Http($Url, $Name, $Attempts = 30) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 5
            Write-Host "${Name}: ready"
            return $response
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$Name did not become ready: $Url"
}

try {
    if ($CleanStart) {
        Write-Host 'Stopping existing Crickzen dashboard and predictor processes...'
        Stop-CricketPredictionProcesses
    }
    Wait-Http 'http://127.0.0.1:8000/health' 'Dashboard' 2 | Out-Null
} catch {
    Start-Process -WindowStyle Hidden -FilePath $Python `
        -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' `
        -WorkingDirectory $DashboardRoot
    Wait-Http 'http://127.0.0.1:8000/health' 'Dashboard' | Out-Null
}

Push-Location $FrontendRoot
try {
    $composeArgs = @('compose', '-f', 'docker-compose.local.yml', 'up', '-d')
    if ($BuildFrontend) { $composeArgs += '--build' }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose startup failed.' }
} finally {
    Pop-Location
}

Wait-Http 'http://localhost:5000/health' 'Scraper' | Out-Null
Wait-Http 'http://localhost:8080/' 'Frontend' | Out-Null
$public = Wait-Http 'http://127.0.0.1:8000/api/public/matches' 'Model feed'
$modelRows = @($public.matches | Where-Object { $_.model_label })
Write-Host ("Model rows: {0}" -f $modelRows.Count)
$modelRows | Select-Object -First 10 slug, model_label, status, updated_at | Format-Table -AutoSize
