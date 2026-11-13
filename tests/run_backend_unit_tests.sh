#!/usr/bin/env bash
# Runs backend/tests/ inside an ephemeral container from the backend image
# (pyzipper + the app's pinned deps live there; the host's python3 is 3.9).
# No database or network involved: the tests only import app.results_zip and
# app.schemas.
#
# Usage: tests/run_backend_unit_tests.sh [image]  (default image: dietnetwork-backend)
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${1:-dietnetwork-backend}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Image '$IMAGE' not found locally -- building from backend/Dockerfile..."
    docker build -f backend/Dockerfile -t "$IMAGE" backend
fi

docker run --rm \
    -v "$(pwd)/backend/tests:/app/tests:ro" \
    --entrypoint bash \
    "$IMAGE" -c "pip install --quiet --no-cache-dir pytest && cd /app && python -m pytest tests -v -p no:cacheprovider"
