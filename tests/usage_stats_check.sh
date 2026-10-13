#!/usr/bin/env bash
# Checks usage statistics (ops/usage_stats.sql) against the isolated test
# stack, after every other check in tests/run_all.sh has submitted its jobs:
#
#   - the positive-control job recorded jobs.sample_count (2504 samples)
#   - the report runs cleanly, prints no email addresses, and its overview
#     totals match direct counts over users/jobs
#   - the since/until period filter excludes jobs outside it
#   - sample_count survives the 30-day retention purge (predictions don't),
#     so the report still counts those samples afterwards
#
# Run LAST: the purge step deletes the positive-control job's results.
#
# Usage: tests/usage_stats_check.sh JOB_ID [EXPECTED_SAMPLES]  (default 2504)
set -uo pipefail
cd "$(dirname "$0")/.."

JOB_ID="$1"
EXPECTED_SAMPLES="${2:-2504}"
PROJECT=dietnet-test
ENV_FILE=tests/.env.test
# shellcheck disable=SC1090
source "$ENV_FILE"

dc() {
    docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f docker-compose.yml -f tests/docker-compose.test.yml "$@"
}
psql_() {
    dc exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 "$@"
}
q() { psql_ -At -c "$1"; } # single value

failures=0
check() {
    if [ "$1" = "$2" ]; then
        echo "  [ok] $3 ($1)"
    else
        echo "  [FAIL] $3 (got '$1', expected '$2')"
        failures=$((failures + 1))
    fi
}
# Overview row of the report as "users_signed_up|...|samples_inferred".
overview() { psql_ -At "$@" < ops/usage_stats.sql | sed -n '/=== Overview ===/{n;p;q}'; }

echo "sample_count recorded:"
check "$(q "SELECT sample_count FROM jobs WHERE id = '$JOB_ID'")" "$EXPECTED_SAMPLES" "positive-control job sample_count"

echo "Report:"
report=$(psql_ < ops/usage_stats.sql)
code=$?
echo "$report" | sed 's/^/  | /'
check "$code" 0 "report ran without SQL errors"
check "$(echo "$report" | grep -c '@')" 0 "no email addresses in the report"

expected="$(q "SELECT count(*) FROM users")|$(q "SELECT count(*) FROM users WHERE is_verified")|$(q "SELECT count(DISTINCT user_id) FROM jobs")|$(q "SELECT count(*) FROM jobs")|$(q "SELECT count(*) FROM jobs WHERE status = 'done'")|$(q "SELECT count(*) FROM jobs WHERE status = 'failed'")|$(q "SELECT count(*) FROM jobs WHERE status IN ('queued', 'running')")|$(q "SELECT coalesce(sum(sample_count), 0) FROM jobs WHERE status = 'done'")"
check "$(overview)" "$expected" "overview totals match direct counts (users|verified|with jobs|submitted|done|failed|in progress|samples)"
check "$(overview -v since=2999-01-01 | cut -d'|' -f4)" 0 "since=2999-01-01 excludes every job"

echo "Retention purge keeps sample_count:"
samples_before=$(overview | cut -d'|' -f8)
q "UPDATE jobs SET created_at = now() - interval '60 days' WHERE id = '$JOB_ID'" >/dev/null
echo "  purged: $(dc exec -T worker python -c 'from worker.cleanup import cleanup_expired_jobs; print(cleanup_expired_jobs())') job(s)"
# cleanup.py's `predictions = None` on a SQLAlchemy JSON column stores JSON
# null, not SQL NULL -- accept either.
check "$(q "SELECT purged_at IS NOT NULL AND coalesce(predictions::text, 'null') = 'null' FROM jobs WHERE id = '$JOB_ID'")" t "job purged (predictions cleared)"
check "$(q "SELECT sample_count FROM jobs WHERE id = '$JOB_ID'")" "$EXPECTED_SAMPLES" "sample_count kept after purge"
check "$(overview | cut -d'|' -f8)" "$samples_before" "report's samples_inferred unchanged by the purge"

if [ "$failures" -ne 0 ]; then
    echo "[FAIL] usage_stats: $failures check(s) failed"
    exit 1
fi
echo "[PASS] usage_stats: sample_count recorded and purge-proof, report totals correct"
