Set-Location $PSScriptRoot

function Fail-Mananze {
  param([string]$Detail)
  if ($Detail) { Write-Host $Detail }
  Write-Host "Python environment not found. Please tell MANANZE."
  pause
  exit 1
}

Write-Host ""
Write-Host "MANANZE — TECHNOCORE AGENT REGISTRY"
Write-Host ""

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
  Fail-Mananze "Python is not installed or not on PATH."
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  $venvPython = Join-Path $PSScriptRoot ".venv/bin/python"
}

if (-not (Test-Path $venvPython)) {
  Write-Host "Creating .venv ..."
  & $pythonCmd.Source -m venv .venv
  if ($LASTEXITCODE -ne 0) {
    Fail-Mananze "Could not create .venv."
  }
  $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    $venvPython = Join-Path $PSScriptRoot ".venv/bin/python"
  }
  if (-not (Test-Path $venvPython)) {
    Fail-Mananze "Could not find the virtualenv Python."
  }
}

& $venvPython -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  Fail-Mananze "Could not install dependencies into .venv."
}

New-Item -ItemType Directory -Force -Path data | Out-Null
if (-not (Test-Path (Join-Path $PSScriptRoot "data\registry.db")) -and -not (Test-Path (Join-Path $PSScriptRoot "data/registry.db"))) {
  $env:PYTHONPATH = "src"
  & $venvPython scripts/seed_demo.py
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Demo seed failed. Check scripts/seed_demo.py and data/ permissions."
    pause
    exit 1
  }
}

$env:PYTHONPATH = "src"
Write-Host ""
Write-Host "Open:                    http://127.0.0.1:8080/"
Write-Host "DID paste demo:          http://127.0.0.1:8080/ui/lookup?did=did:example:test-document"
Write-Host "Leave this window open. Close it to stop the demo."
Write-Host ""
& $venvPython -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
if ($LASTEXITCODE -ne 0) {
  Write-Host "Server stopped with an error. Check that port 8080 is free and .venv is intact."
  pause
  exit 1
}
