$ErrorActionPreference = "Stop"

$DashboardRoot = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $DashboardRoot

$env:PROJECT_ROOT = $ProjectRoot
$env:PYTHONPATH = "$ProjectRoot\src;$DashboardRoot"

Set-Location $DashboardRoot

& "$DashboardRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
