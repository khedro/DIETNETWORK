#!/usr/bin/env bash
# Orchestrates TESTING.md end to end against an isolated, throwaway stack:
# generates fixtures, brings the stack up under its own compose project
# (never touches whatever's already running under the default
# "dietnetwork" project on this host), runs every check, prints a
# diagnostics summary, and tears the stack down.
#
# Usage: tests/run_all.sh [--keep] [--skip-fixtures]
#   --keep           leave the isolated stack running afterward (for
#                     debugging a failure) instead of tearing it down
#   --skip-fixtures  don't regenerate dataTest/fixtures/ (they're
#                     deterministic -- only useful to skip if you know
#                     they're already current)
set -uo pipefail
cd "$(dirname "$0")/.."

PROJECT=dietnet-test
ENV_FILE=tests/.env.test
BASE_URL=http://localhost:18000
MAILHOG_URL=http://localhost:18025

# Everything this harness writes on the host stays inside the repo (this
# server's /tmp is off limits): scratch files in tests/.tmp, host-side Python
# deps (requests, pyzipper) in tests/.venv. Both are gitignored.
TMP_DIR=tests/.tmp
mkdir -p "$TMP_DIR"
export TMPDIR="$(pwd)/$TMP_DIR"
VENV=tests/.venv
if [ ! -x "$VENV/bin/python" ]; then
    # Python 3.11 when available (also runs the pure unit tests on the host);
    # the system python3 here is 3.9.
    "$(command -v python3.11 || command -v python3)" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet requests pyzipper==0.3.6 pytest pydantic==2.9.2 email-validator==2.2.0
fi
PY="$VENV/bin/python"

KEEP=0
SKIP_FIXTURES=0
for arg in "$@"; do
    case "$arg" in
        --keep) KEEP=1 ;;
        --skip-fixtures) SKIP_FIXTURES=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

dc() {
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml -f tests/docker-compose.test.yml "$@"
}

RESULTS=() # "NAME:PASS" or "NAME:FAIL", printed as the final summary

record() {
    local name="$1" code="$2"
    if [ "$code" -eq 0 ]; then
        RESULTS+=("$name:PASS")
    else
        RESULTS+=("$name:FAIL")
    fi
}

cleanup() {
    if [ "$KEEP" -eq 1 ]; then
        echo
        echo "--keep set: leaving stack up (project '$PROJECT', backend at $BASE_URL, mailhog at $MAILHOG_URL)"
        echo "Tear down later with: docker compose -p $PROJECT --env-file $ENV_FILE -f docker-compose.yml -f tests/docker-compose.test.yml down"
    else
        echo
        echo "Tearing down isolated stack..."
        dc down --volumes
    fi
}
trap cleanup EXIT

wait_for_backend() {
    for _ in $(seq 1 60); do
        if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    echo "backend did not become healthy within 120s" >&2
    return 1
}

echo "=== Generating pre-flight fixtures ==="
if [ "$SKIP_FIXTURES" -eq 0 ]; then
    "$PY" tests/fixtures/generate_fixtures.py
else
    echo "(skipped, --skip-fixtures)"
fi

echo
echo "=== Preparing data volume ==="
# Docker auto-creates DATA_HOST_PATH/uploads as root on first bind-mount if
# it doesn't already exist, but backend/worker both run as uid 10001 (see
# their Dockerfiles' `useradd -u 10001`) and never run as root -- so an
# unprepared volume 500s on the very first upload (PermissionError on
# /data/<job_id>). Pre-create and chown it ourselves rather than relying on
# either container to fix its own mount.
mkdir -p tests/.volumes-test/uploads
docker run --rm -v "$(pwd)/tests/.volumes-test/uploads:/v" alpine chown -R 10001:10001 /v

echo
echo "=== Bringing up isolated stack (project: $PROJECT) ==="
dc up -d --build postgres redis mailhog backend worker beat
wait_for_backend || { record "stack-startup" 1; echo "Cannot continue without a healthy backend."; exit 1; }
record "stack-startup" 0

echo
echo "=== Unit tests (worker/tests/test_pipeline.py) ==="
./tests/run_unit_tests.sh "${PROJECT}-worker"
record "unit-tests-worker" $?

echo
echo "=== Unit tests (backend/tests/test_results_zip.py) ==="
./tests/run_backend_unit_tests.sh "${PROJECT}-backend"
record "unit-tests-backend" $?

echo
echo "=== Pre-flight: positive control (section 1) ==="
"$PY" tests/preflight_checks.py --case positive --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL" \
    --json-out "$TMP_DIR/positive.json"
record "preflight-positive" $?

echo
echo "=== Pre-flight: 2a SNP overlap < 1000 ==="
"$PY" tests/preflight_checks.py --case 2a --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2a-snp-overlap" $?

echo
echo "=== Pre-flight: 2b swapped alleles ==="
"$PY" tests/preflight_checks.py --case 2b --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2b-harmonization" $?

echo
echo "=== Pre-flight: 2e rsID-labeled SNP IDs (relabeled by position, runs to completion) ==="
"$PY" tests/preflight_checks.py --case 2e --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2e-id-relabel" $?

echo
echo "=== One active job per user (uploads.py's queued/running gate) ==="
"$PY" tests/one_active_job_check.py --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "one-active-job-per-user" $?

echo
echo "=== Result outputs: encrypted zip, results table, job log (positive-control job) ==="
if [ -f "$TMP_DIR/positive.json" ]; then
    JOB_ID=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['job_id'])" "$TMP_DIR/positive.json")
    ACCESS_TOKEN=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['access_token'])" "$TMP_DIR/positive.json")
    "$PY" tests/results_outputs_check.py --base-url "$BASE_URL" --job-id "$JOB_ID" \
        --access-token "$ACCESS_TOKEN" --work-dir "$TMP_DIR"
    record "result-outputs" $?
else
    echo "Skipped: no completed job from the positive-control step." >&2
    record "result-outputs" 1
fi

echo
echo "=== Pre-flight: 2c sample count cap (MAX_SAMPLES temporarily lowered to 2000) ==="
MAX_SAMPLES=2000 dc up -d --no-deps worker
sleep 5
"$PY" tests/preflight_checks.py --case 2c --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2c-sample-cap" $?
dc up -d --no-deps worker # restore default (10000)
sleep 5

echo
echo "=== Pre-flight: 2d upload size cap (MAX_UPLOAD_MB temporarily lowered to 5) ==="
MAX_UPLOAD_MB=5 dc up -d --no-deps backend
wait_for_backend
"$PY" tests/preflight_checks.py --case 2d --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL"
record "preflight-2d-upload-size" $?
dc up -d --no-deps backend # restore default (1024)
wait_for_backend

echo
echo "=== FCFS processing queue (section 4; CELERY_WORKER_CONCURRENCY temporarily set to 1) ==="
CELERY_WORKER_CONCURRENCY=1 dc up -d --no-deps worker
sleep 5
echo "Worker concurrency now: $(dc exec -T worker sh -c 'echo $CELERY_WORKER_CONCURRENCY')"
# Live worker log for the duration of the test, kept for the report.
dc logs -f --timestamps --no-log-prefix --since 1s worker > "$TMP_DIR/fcfs_worker.log" 2>&1 &
LOGS_PID=$!
"$PY" tests/fcfs_queue_check.py --base-url "$BASE_URL" --mailhog-url "$MAILHOG_URL" --n 5
record "fcfs-queue" $?
sleep 2
kill "$LOGS_PID" 2>/dev/null
echo "--- worker log during the FCFS test (task lifecycle lines) ---"
grep -E "Task worker.tasks.run_inference_job|Job [0-9a-f-]+ failed|ready\.|concurrency" "$TMP_DIR/fcfs_worker.log" | cut -c1-220
dc up -d --no-deps worker # restore default (9)
sleep 5

echo
echo "=== Download concurrency cap (section 5) ==="
if [ -f "$TMP_DIR/positive.json" ]; then
    JOB_ID=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['job_id'])" "$TMP_DIR/positive.json")
    ACCESS_TOKEN=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['access_token'])" "$TMP_DIR/positive.json")
    "$PY" tests/download_concurrency_check.py --base-url "$BASE_URL" \
        --job-id "$JOB_ID" --access-token "$ACCESS_TOKEN" --limit 9 --requests 15 --rounds 3
    record "download-concurrency" $?
else
    echo "Skipped: no completed job from the positive-control step to download." >&2
    record "download-concurrency" 1
fi

echo
echo "================= SUMMARY ================="
overall=0
for r in "${RESULTS[@]}"; do
    name="${r%%:*}"
    status="${r##*:}"
    printf '%-32s %s\n' "$name" "$status"
    [ "$status" = "FAIL" ] && overall=1
done
echo "============================================="
exit $overall
