#!/usr/bin/env bash
# Build the standalone coverity-metrics binary on Linux using PyInstaller.
# Assumes `pip install -e .[build]` has been run in the active environment.

set -euo pipefail

PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "Building coverity-metrics binary..."
echo "  repo root : $REPO_ROOT"
echo "  python    : $PYTHON"

"$PYTHON" -m PyInstaller packaging/coverity-metrics.spec --clean --noconfirm

BIN="$REPO_ROOT/dist/coverity-metrics"
if [[ ! -f "$BIN" ]]; then
    echo "ERROR: Expected binary not found: $BIN" >&2
    exit 1
fi

echo
echo "Smoke test: $BIN dashboard --version"
"$BIN" dashboard --version || echo "WARNING: smoke test returned non-zero"

SIZE_MB=$(du -m "$BIN" | cut -f1)
echo
echo "Built: $BIN (${SIZE_MB} MB)"
