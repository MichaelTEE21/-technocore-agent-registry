@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo.
echo MANANZE — TECHNOCORE AGENT REGISTRY
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python is not installed or not on PATH.
  echo Python environment not found. Please tell MANANZE.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo Could not create .venv.
    echo Python environment not found. Please tell MANANZE.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo Python environment not found. Please tell MANANZE.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo Could not install dependencies into .venv.
  echo Python environment not found. Please tell MANANZE.
  pause
  exit /b 1
)

if not exist data mkdir data
if not exist data\registry.db (
  set PYTHONPATH=src
  ".venv\Scripts\python.exe" scripts\seed_demo.py
  if errorlevel 1 (
    echo Demo seed failed. Check scripts\seed_demo.py and data\ permissions.
    pause
    exit /b 1
  )
)

set PYTHONPATH=src
echo.
echo Open:                    http://127.0.0.1:8080/
echo DID paste demo:          http://127.0.0.1:8080/ui/lookup?did=did:example:test-document
echo Leave this window open. Close it to stop the demo.
echo.
".venv\Scripts\python.exe" -m uvicorn tar.main:app --host 127.0.0.1 --port 8080
if errorlevel 1 (
  echo Server stopped with an error. Check that port 8080 is free and .venv is intact.
)
pause
