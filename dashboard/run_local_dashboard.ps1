$ErrorActionPreference = "Stop"

$DashboardRoot = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $DashboardRoot

$env:PROJECT_ROOT = $ProjectRoot
$env:PYTHONPATH = "$ProjectRoot\src;$DashboardRoot"

$Python = Join-Path $DashboardRoot ".venv313\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = Join-Path $DashboardRoot ".venv\Scripts\python.exe"
}

Set-Location $DashboardRoot

& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
