---
title: Usage statistics (ops/usage_stats.sql)
type: code
sources: [code]
updated: 2026-10-30
---

# Usage statistics

Platform usage numbers for grant proposals and Alliance (Compute Canada) resource
applications, computed on demand from the `users` and `jobs` tables by
[ops/usage_stats.sql](../../ops/usage_stats.sql). Added in `e54b406` at the team's
request: number of users, jobs submitted and successful per user, samples inferred,
and positions per analysis.

## What it reports

| Section | Numbers | Source columns |
|---|---|---|
| Overview | users signed up / verified / with jobs; jobs submitted, successful, failed, in progress; samples inferred | `users`, `jobs.status`, `jobs.sample_count` |
| Per user | jobs submitted, successful, samples inferred | `jobs.user_id`; users shown as "user N" (sign-up order), never email or ID |
| Positions per successful analysis | min, median, mean, max panel SNPs used; panel size | `jobs.snp_overlap_count`, `snp_overlap_total` |
| Per month | active users, jobs, successes, samples | `jobs.created_at` |

Optional reporting period on job and sign-up dates:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v since=2026-01-01 -v until=2027-01-01 < ops/usage_stats.sql
```

The script is read-only (plain `SELECT`s plus a session-scoped temp view). Its output
is not stored anywhere; redirect it to a file to keep a copy for a report.

## Where the numbers come from

- **`jobs.sample_count`** is the one column added for this
  ([Alembic 5c1d2e7a9b40](../../backend/alembic/versions/5c1d2e7a9b40_job_sample_count.py),
  [models.py:87](../../backend/app/models.py#L87), mirrored in
  [worker db.py:49](../../worker/worker/db.py#L49)). The worker sets it when a job
  succeeds ([tasks.py:208](../../worker/worker/tasks.py#L208)).
- Everything else already existed. The 30-day purge clears files and `predictions`
  but keeps the job row, so all these columns survive it
  ([worker pipeline: retention](worker-pipeline.md#retention)).
- "Positions per analysis" means panel positions the models actually used. The total
  number of positions in each uploaded file is only in the per-job log file, which the
  purge deletes; it is not stored in the database.

## Limits

- **Samples are counted from deployment onward.** Jobs that ran before `5c1d2e7a9b40`
  have no `sample_count`, and once purged their sample count cannot be recovered. On
  the local ICM stack (checked 2026-10-30) all 15 jobs date from Aug–Sep 2026 and show
  0 samples for that reason.
- Deleting a user cascades to their jobs (`ON DELETE CASCADE`), removing them from the
  statistics. No account-deletion feature exists yet.
- **No database backup exists** (no `pg_dump`, snapshot or backup job in the repo).
  Losing the Cinder volume would lose all statistics. See [Deployment](deployment.md).
- Per-user rows are pseudonymous, not anonymous: "user N" maps back to `users` in the
  database. Use the totals in grant documents.

## Tested by

[tests/usage_stats_check.sh](../../tests/usage_stats_check.sh), the last step of
`tests/run_all.sh` (see [Testing](testing.md)): `sample_count` recorded for the
positive control (2504), report totals match direct counts, the period filter works,
and `sample_count` survives a simulated purge.

## See also
- [Worker pipeline](worker-pipeline.md)
- [Web platform](web-platform.md)
- [Deployment](deployment.md)
- [Testing](testing.md)
