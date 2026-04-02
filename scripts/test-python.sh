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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -d "${REPO_ROOT}/packages/python" ]]; then
    # Invoked from repo root (or anywhere) via scripts/test-python.sh
    cd "${REPO_ROOT}/packages/python"
elif [[ -f "pyproject.toml" && -d "tests" && -d "src" ]]; then
    # Already in packages/python
    :
else
    echo "Error: cannot locate packages/python from current working directory: $(pwd)" >&2
    exit 1
fi

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
