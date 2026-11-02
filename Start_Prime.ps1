$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$primePython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $primePython)) {
    Write-Host "Copy the updated code into your existing project folder containing .venv."
    exit 1
}
& $primePython -m uvicorn main:app --host 127.0.0.1 --port 8000
