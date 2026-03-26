@echo off
:: =============================================================================
:: run_tests.bat — Webshop Playwright Test Runner (Windows)
::
:: Usage:
::   run_tests.bat              :: local Docker  (http://localhost)
::   run_tests.bat --local      :: local Docker  (http://localhost)
::   run_tests.bat --dev        :: Vite dev server (http://localhost:5173)
::   run_tests.bat --prod       :: production    (https://webshop.xpert-hub.com)
::   run_tests.bat --url https://custom.example.com
::
:: Any extra arguments are forwarded to pytest, e.g.:
::   run_tests.bat --prod -m smoke
::   run_tests.bat --prod test_auth.py -v
:: =============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: ---------------------------------------------------------------------------
:: Parse flags
:: ---------------------------------------------------------------------------
set TARGET_URL=
set PYTEST_EXTRA=

:parse_args
if "%~1"=="" goto end_parse
if /i "%~1"=="--local" (
    set TARGET_URL=http://localhost
    shift
    goto parse_args
)
if /i "%~1"=="--dev" (
    set TARGET_URL=http://localhost:5173
    shift
    goto parse_args
)
if /i "%~1"=="--prod" (
    set TARGET_URL=https://webshop.xpert-hub.com
    shift
    goto parse_args
)
if /i "%~1"=="--url" (
    set TARGET_URL=%~2
    shift
    shift
    goto parse_args
)
:: Anything else is forwarded to pytest
set PYTEST_EXTRA=!PYTEST_EXTRA! %1
shift
goto parse_args
:end_parse

:: Fall back to BASE_URL env var, then default to local
if "!TARGET_URL!"=="" (
    if defined BASE_URL (
        set TARGET_URL=!BASE_URL!
    ) else (
        set TARGET_URL=http://localhost
    )
)

:: ---------------------------------------------------------------------------
:: Banner
:: ---------------------------------------------------------------------------
echo ============================================
echo  Webshop Playwright Test Suite
echo ============================================
echo  Target : !TARGET_URL!
echo ============================================
echo.

:: ---------------------------------------------------------------------------
:: Verify Python is available
:: ---------------------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.9+ and ensure it is on PATH.
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: Install dependencies if not already installed
:: ---------------------------------------------------------------------------
echo [INFO] Installing / verifying Python dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies from requirements.txt
    exit /b 1
)

echo [INFO] Installing Playwright browsers...
python -m playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser install returned non-zero (may already be up to date)
)

if not exist "test-results\screenshots" mkdir "test-results\screenshots"
if not exist "test-results\videos"      mkdir "test-results\videos"
if not exist "reports"                  mkdir "reports"

:: ---------------------------------------------------------------------------
:: Run  (use "python -m pytest" so it works regardless of PATH)
:: ---------------------------------------------------------------------------
python -m pytest ^
  --base-url=!TARGET_URL! ^
  --screenshot=on ^
  --video=retain-on-failure ^
  --tracing=retain-on-failure ^
  --output=test-results ^
  --html=reports/report.html ^
  --self-contained-html ^
  -v ^
  --tb=short ^
  !PYTEST_EXTRA!

set EXIT_CODE=%errorlevel%

:: ---------------------------------------------------------------------------
:: Summary
:: ---------------------------------------------------------------------------
echo.
echo ============================================
if %EXIT_CODE% equ 0 (
    echo  ALL TESTS PASSED
) else (
    echo  SOME TESTS FAILED  (exit: %EXIT_CODE%)
)
echo ============================================
echo.
echo  Target     : !TARGET_URL!
echo  HTML Report: reports\report.html
echo  Artifacts  : test-results\
echo.

exit /b %EXIT_CODE%
