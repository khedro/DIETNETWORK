#!/usr/bin/env bash
# 12 simulated users on the real website in headless Chromium, against an isolated
# copy of the production topology (Caddy + TLS, frontend, backend, worker, beat,
# postgres, redis, MailHog). Never touches the "dietnetwork" stack on this host.
#
#   1. makes 12 separate 50-sample uploads (PLINK, VCF, bgen, one to be rejected)
#   2. starts the stack with a clean database and data folder
#   3. runs simulate.cjs while sampling CPU, memory, load and disk
#   4. collects the database, emails and usage report, then writes
#      tests/e2e/.work/out/report.md (analyze.py)
#   5. tears the stack down and deletes its data
#
# Usage: tests/e2e/run.sh [--keep]   (--keep leaves the stack up for debugging)
set -uo pipefail
cd "$(dirname "$0")/../.."

PROJECT=dietnet-e2e
ENV_FILE=tests/e2e/.env.e2e
WORK="$(pwd)/tests/e2e/.work"
OUT="$WORK/out"
SRC_DIR="${SRC_DIR:-/home/okhedr/DIETNETWORK/dataTest}"
SRC_NAME=1000G.2504_WGS30x.GSA17k_MHI.intersectGSA.miss10perc.maf0.05.pruned.autosomes.noHLA.phased_imputed
PW_IMAGE=mcr.microsoft.com/playwright:v1.64.1-noble
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1
ME="$(id -u):$(id -g)"

# shellcheck disable=SC1090
source "$ENV_FILE"

dc() {
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml -f tests/e2e/docker-compose.e2e.yml "$@"
}

wipe_volumes() {
    # postgres/ and uploads/ belong to the containers' users.
    if [ -d "$WORK/volumes" ]; then
        docker run --rm -v "$WORK/volumes:/v" alpine sh -c 'rm -rf /v/postgres /v/uploads'
    fi
}

cleanup() {
    touch "$OUT/.stop-metrics"
    if [ "$KEEP" -eq 1 ]; then
        echo "--keep: stack left up (https://localhost:18443). Tear down with: dc down --volumes"
    else
        echo "=== Tearing down ==="
        dc down --volumes --remove-orphans >/dev/null 2>&1
        wipe_volumes
    fi
}

mkdir -p "$WORK/data"
wipe_volumes
rm -rf "$OUT"
mkdir -p "$OUT" "$WORK/volumes/uploads"
docker run --rm -v "$WORK/volumes/uploads:/v" alpine chown -R 10001:10001 /v
trap cleanup EXIT

echo "=== Building images ==="
dc build backend worker beat frontend 2>&1 | tail -3 || exit 1

if [ ! -f "$WORK/data/expected.json" ]; then
    echo "=== Making the 12 uploads ==="
    docker run --rm --user "$ME" \
        -v "$SRC_DIR:/src:ro" -v "$WORK/data:/out" -v "$(pwd)/tests/e2e/make_data.py:/make_data.py:ro" \
        --entrypoint python "${PROJECT}-worker" /make_data.py "/src/$SRC_NAME" /src/fixtures/low_overlap.bim /out \
        || { echo "Data generation failed"; exit 1; }
fi

echo "=== Starting the stack (project: $PROJECT) ==="
dc up -d postgres redis mailhog backend worker beat frontend edge 2>&1 | tail -2
ready=0
for _ in $(seq 1 90); do
    if curl -skf https://localhost:18443/api/health >/dev/null; then ready=1; break; fi
    sleep 2
done
if [ "$ready" -ne 1 ]; then
    echo "Stack did not become healthy"
    dc ps
    dc logs --tail 30 backend edge
    exit 1
fi
echo "Stack healthy at https://localhost:18443"

echo "=== Installing the Playwright client ==="
docker run --rm --user "$ME" -e HOME=/tmp -v "$WORK:/work" -w /work "$PW_IMAGE" \
    npm install --no-audit --no-fund --silent playwright-core@1.64.1 || { echo "npm install failed"; exit 1; }

./tests/e2e/sample_metrics.sh "$PROJECT" "$OUT/metrics.csv" "$OUT/.stop-metrics" 5 &
METRICS_PID=$!

echo "=== Running 12 users ==="
docker run --rm --user "$ME" -e HOME=/tmp --network host --shm-size=2g \
    -e NODE_PATH=/work/node_modules -e DATA_DIR=/work/data -e OUT_DIR=/work/out -e SIM_USERS="${SIM_USERS:-}" \
    -v "$WORK:/work" -v "$(pwd)/tests/e2e/simulate.cjs:/simulate.cjs:ro" \
    "$PW_IMAGE" node /simulate.cjs
SIM_CODE=$?
echo "Simulation exit code: $SIM_CODE"

touch "$OUT/.stop-metrics"
wait "$METRICS_PID"

echo "=== Collecting database, emails and usage report ==="
psql_() { dc exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"; }
psql_ -v ON_ERROR_STOP=1 < ops/usage_stats.sql > "$OUT/usage_stats.txt" 2>&1
psql_ -At -c "SELECT coalesce(json_agg(row_to_json(t)), '[]') FROM (
    SELECT u.email, j.id, j.user_id, j.status, j.input_type, j.sample_count, j.snp_overlap_count,
           j.snp_overlap_total, j.is_reliable, j.created_at, j.started_at, j.completed_at, j.raw_deleted_at, j.error_message
    FROM jobs j JOIN users u ON u.id = j.user_id ORDER BY j.created_at) t" > "$OUT/jobs_raw.json"
dc logs --no-log-prefix worker > "$OUT/worker.log" 2>&1
dc logs --no-log-prefix backend > "$OUT/backend.log" 2>&1
curl -s "http://127.0.0.1:18125/api/v2/messages?limit=500" > "$OUT/mailhog.json"
dc exec -T worker find /data -mindepth 3 -maxdepth 3 -type d > "$OUT/data_dirs.txt"

cat > "$OUT/.prepare.py" <<'EOF'
import json
jobs = json.load(open("/out/jobs_raw.json"))
dirs = set(open("/out/data_dirs.txt").read().split())
for j in jobs:
    j["raw_exists"] = f"/data/{j['user_id']}/{j['id']}/raw" in dirs
json.dump(jobs, open("/out/jobs.json", "w"), indent=1)
emails = {}
for item in json.load(open("/out/mailhog.json")).get("items", []):
    to = item["Content"]["Headers"].get("To", [""])[0].split("@")[0]
    emails.setdefault(to, []).append(item["Content"]["Headers"].get("Subject", [""])[0])
json.dump(emails, open("/out/emails.json", "w"), indent=1)
EOF

echo "=== Report ==="
docker run --rm --user "$ME" -v "$OUT:/out" -v "$WORK/data:/data:ro" \
    -v "$(pwd)/tests/e2e/analyze.py:/analyze.py:ro" --entrypoint sh "${PROJECT}-backend" \
    -c 'python /out/.prepare.py && python /analyze.py /data /out'
REPORT_CODE=$?

echo "Simulation exit: $SIM_CODE, report exit: $REPORT_CODE"
[ "$SIM_CODE" -eq 0 ] && [ "$REPORT_CODE" -eq 0 ]
