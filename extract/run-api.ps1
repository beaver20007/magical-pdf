# Start Extract FastAPI (magical-pdf sidecar)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Create venv first: py -3.11 -m venv .venv; pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

$env:HF_HUB_DISABLE_SSL_VERIFICATION = "1"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Extract API http://127.0.0.1:8765" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --reload --port 8765
