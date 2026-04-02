#!/usr/bin/env bash
set -euo pipefail

# Shared test command for mcp-refcache Python package.
# Used by both lefthook (pre-push) and CI.
#
# Usage:
#   ./scripts/test-python.sh           # pre-push: tests + coverage report (no threshold)
#   ./scripts/test-python.sh --ci      # CI: tests + coverage + enforces >=80% threshold

COV_TARGET="src/mcp_refcache"
COV_THRESHOLD=80

cd packages/python

if [[ "${1:-}" == "--ci" ]]; then
    echo "=== CI mode: enforcing coverage >= ${COV_THRESHOLD}% ==="
    uv run pytest \
        --cov="${COV_TARGET}" \
        --cov-report=term-missing \
        --cov-report=xml \
        --cov-fail-under="${COV_THRESHOLD}"
else
    echo "=== Pre-push mode: tests + coverage report (no threshold) ==="
    uv run pytest -q \
        --cov="${COV_TARGET}" \
        --cov-report=term-missing:skip-covered
fi
