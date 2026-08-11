@echo off
REM 🚀 AI SHOP PRO - ENDPOINT TESTING SUITE (Windows)
REM This script tests all endpoints with the provided database

setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════════════════════
echo   🧪 AI SHOP PRO - ENDPOINT TESTING SUITE LAUNCHER
echo ════════════════════════════════════════════════════════════════
echo.

REM Check if .env.production exists
if not exist .env.production (
    echo ❌ .env.production file not found!
    echo Please create .env.production with DATABASE_URL
    pause
    exit /b 1
)

echo ✅ .env.production found

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not installed or not in PATH
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYVERSION=%%i
echo ✅ Python found: %PYVERSION%

REM Install requirements
echo.
echo 📦 Installing dependencies...
pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed

REM Start test
echo.
echo Starting comprehensive endpoint tests...
echo.

python test_all_endpoints_comprehensive.py

REM Capture exit code
set EXIT_CODE=%errorlevel%

echo.
echo ════════════════════════════════════════════════════════════════

if %EXIT_CODE% equ 0 (
    echo ✅ ALL TESTS PASSED!
) else (
    echo ⚠️  Some tests failed - check test_report_*.json for details
)

pause
exit /b %EXIT_CODE%
