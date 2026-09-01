Set-Location $PSScriptRoot
Write-Host "Technocore Agent Registry - local demo (not official Technocore)"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is not installed. Install Python 3.12+ from python.org and tick Add to PATH."
  pause
  exit 1
}
if (-not (Test-Path .venv)) {
  Write-Host "Creating .venv ..."
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install -q -r requirements.txt
New-Item -ItemType Directory -Force -Path data | Out-Null
if (-not (Test-Path data\registry.db)) {
  python scripts/seed_demo.py
}
$env:PYTHONPATH = "src"
Write-Host ""
Write-Host "Open Chrome and go to:  http://127.0.0.1:8080/"
Write-Host "Try a DID paste:        http://127.0.0.1:8080/ui/lookup?did=did:example:test-document"
Write-Host "Leave this window open. Close it to stop the demo."
Write-Host ""
python -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
