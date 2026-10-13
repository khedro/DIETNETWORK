-- Platform usage statistics (grant proposals, Compute Canada / Alliance
-- resource applications). Read-only: plain SELECTs over users and jobs.
--
-- Usage (from the repo root, against the running stack):
--   docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < ops/usage_stats.sql
-- Optional reporting period on job/sign-up dates (inclusive, half-open on `until`):
--   docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--     -v since=2026-01-01 -v until=2027-01-01 < ops/usage_stats.sql
--
-- Users are listed as "user N" (N = sign-up order), never by email or ID, so
-- the output can be pasted into a report. Samples come from jobs.sample_count,
-- which is recorded for successful jobs and survives the 30-day purge.
-- Positions = Diet Network panel SNPs found in the upload and used by the
-- models (jobs.snp_overlap_count, out of snp_overlap_total).

\set QUIET on
\if :{?since}
\else
\set since 1900-01-01
\endif
\if :{?until}
\else
\set until 9999-01-01
\endif
\pset footer off
\pset null '-'

CREATE TEMP VIEW period_jobs AS
SELECT * FROM jobs
WHERE created_at >= :'since'::date AND created_at < :'until'::date;

\echo
\echo '=== Overview ==='
SELECT
    (SELECT count(*) FROM users
      WHERE created_at >= :'since'::date AND created_at < :'until'::date)      AS users_signed_up,
    (SELECT count(*) FROM users WHERE is_verified
      AND created_at >= :'since'::date AND created_at < :'until'::date)        AS users_verified,
    (SELECT count(DISTINCT user_id) FROM period_jobs)                         AS users_with_jobs,
    count(*)                                                                  AS jobs_submitted,
    count(*) FILTER (WHERE status = 'done')                                   AS jobs_successful,
    count(*) FILTER (WHERE status = 'failed')                                 AS jobs_failed,
    count(*) FILTER (WHERE status IN ('queued', 'running'))                   AS jobs_in_progress,
    coalesce(sum(sample_count) FILTER (WHERE status = 'done'), 0)             AS samples_inferred
FROM period_jobs;

\echo
\echo '=== Per user (users with at least one job) ==='
SELECT
    'user ' || u.n                                    AS "user",
    count(j.id)                                       AS jobs_submitted,
    count(j.id) FILTER (WHERE j.status = 'done')      AS jobs_successful,
    coalesce(sum(j.sample_count) FILTER (WHERE j.status = 'done'), 0) AS samples_inferred
FROM (SELECT id, row_number() OVER (ORDER BY created_at, id) AS n FROM users) u
JOIN period_jobs j ON j.user_id = u.id
GROUP BY u.n
ORDER BY u.n;

\echo
\echo '=== Positions per successful analysis (panel SNPs used) ==='
SELECT
    count(*)                                                                  AS analyses,
    min(snp_overlap_count)                                                    AS min_positions,
    percentile_disc(0.5) WITHIN GROUP (ORDER BY snp_overlap_count)            AS median_positions,
    round(avg(snp_overlap_count))                                             AS mean_positions,
    max(snp_overlap_count)                                                    AS max_positions,
    max(snp_overlap_total)                                                    AS panel_size
FROM period_jobs
WHERE status = 'done';

\echo
\echo '=== Per month ==='
SELECT
    to_char(date_trunc('month', created_at), 'YYYY-MM')                       AS month,
    count(DISTINCT user_id)                                                   AS active_users,
    count(*)                                                                  AS jobs_submitted,
    count(*) FILTER (WHERE status = 'done')                                   AS jobs_successful,
    coalesce(sum(sample_count) FILTER (WHERE status = 'done'), 0)             AS samples_inferred
FROM period_jobs
GROUP BY 1
ORDER BY 1;
