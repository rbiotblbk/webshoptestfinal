#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — Webshop Playwright Test Runner
#
# Usage:
#   ./run_tests.sh              # local Docker  (http://localhost)
#   ./run_tests.sh --local      # local Docker  (http://localhost)
#   ./run_tests.sh --dev        # Vite dev server (http://localhost:5173)
#   ./run_tests.sh --prod       # production    (https://webshop.xpert-hub.com)
#   ./run_tests.sh --url https://custom.example.com
#
# Any extra arguments are forwarded directly to pytest, e.g.:
#   ./run_tests.sh --prod -m smoke
#   ./run_tests.sh --prod test_auth.py -v
# =============================================================================
set -e
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# Parse our own flags before passing remaining args to pytest
# ---------------------------------------------------------------------------
TARGET_URL=""
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      TARGET_URL="http://localhost"
      shift
      ;;
    --dev)
      TARGET_URL="http://localhost:5173"
      shift
      ;;
    --prod)
      TARGET_URL="https://webshop.xpert-hub.com"
      shift
      ;;
    --url)
      TARGET_URL="$2"
      shift 2
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

# Fall back to BASE_URL env var, then default to local
if [[ -z "$TARGET_URL" ]]; then
  TARGET_URL="${BASE_URL:-http://localhost}"
fi

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo "============================================"
echo " Webshop Playwright Test Suite"
echo "============================================"
echo " Target : $TARGET_URL"
echo " Date   : $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
echo "[INFO] Installing / verifying Python dependencies..."
python -m pip install -q -r requirements.txt

echo "[INFO] Installing Playwright browsers..."
python -m playwright install chromium

mkdir -p test-results/screenshots test-results/videos reports

# ---------------------------------------------------------------------------
# Run  (python -m pytest works regardless of PATH)
# ---------------------------------------------------------------------------
python -m pytest \
  --base-url="$TARGET_URL" \
  --screenshot=on \
  --video=retain-on-failure \
  --tracing=retain-on-failure \
  --output=test-results \
  --html=reports/report.html \
  --self-contained-html \
  -v \
  --tb=short \
  "${PYTEST_ARGS[@]}"

EXIT_CODE=$?

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
if [ $EXIT_CODE -eq 0 ]; then
  echo " ALL TESTS PASSED"
else
  echo " SOME TESTS FAILED  (exit: $EXIT_CODE)"
fi
echo "============================================"
echo ""
echo " Target     : $TARGET_URL"
echo " HTML Report: reports/report.html"
echo " Artifacts  : test-results/"
echo ""

exit $EXIT_CODE
