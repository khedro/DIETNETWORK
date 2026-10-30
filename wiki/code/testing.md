---
title: Testing (tests/, worker/tests/, backend/tests/)
type: code
sources: [code]
updated: 2026-10-30
---

# Testing

The platform has pure unit tests for the worker and backend, and an end-to-end suite
that brings up an isolated copy of the whole stack, runs real jobs through it and
tears it down. The plan behind it is [TESTING.md](../../TESTING.md); its own results
table is out of date (see [Repo docs](../sources/repo-docs.md#testingmd)).

## Unit tests

| Suite | Runs in | Covers |
|---|---|---|
| [worker/tests/test_pipeline.py](../../worker/tests/test_pipeline.py) (23 tests) | worker image, via [tests/run_unit_tests.sh](../../tests/run_unit_tests.sh) | sample count, SNP overlap with real PLINK, allele harmonization classes, ID-labeling detection, position-based relabel, results table and consensus, job log, missing rates |
| [backend/tests/test_results_zip.py](../../backend/tests/test_results_zip.py) (6 tests) | backend image, via [tests/run_backend_unit_tests.sh](../../tests/run_backend_unit_tests.sh) | AES-256 zip opens only with the right password, keeps its layout, rejects short passwords |

Both run in Docker because the host's `python3` is 3.9 and the code needs 3.10+.

## End-to-end suite: `tests/run_all.sh`

[run_all.sh](../../tests/run_all.sh) uses its own compose project (`dietnet-test`,
backend on :18000, MailHog on :18025, data in `tests/.volumes-test/`), so it never
touches the `dietnetwork` stack. Steps, in order:

| Check | What it proves |
|---|---|
| stack-startup | images build, migrations apply, backend healthy |
| unit tests (worker, backend) | the two suites above |
| preflight positive | 2504-sample 1KGP control runs all 15 models, overlap 229,986/229,986 |
| 2a / 2b / 2e | low overlap rejected; swapped alleles rejected; rsID-labelled IDs relabelled and run |
| one-active-job-per-user | second upload gets `409` until the first job finishes |
| result-outputs | encrypted zip, results table columns and consensus, job log, API predictions |
| 2c / 2d | sample cap and upload size cap (limits lowered temporarily) |
| fcfs-queue | queue order and one-at-a-time execution with concurrency 1 |
| download-concurrency | 9 × `200` and 6 × `429` for 15 parallel downloads, 3 rounds |
| usage-stats | `sample_count` and [usage statistics](usage-statistics.md); runs last because it purges the positive-control job |

## Latest results

| Run | Result |
|---|---|
| 2026-10-13 (after `e54b406`) | 12/14; usage-stats failed on a test bug (JSON `null` vs SQL `NULL`), fixed and re-run: pass |
| 2026-10-27 (with an uncommitted Node 22 frontend image) | **13/14**; only fcfs-queue failed |

### Known test bug: fcfs-queue

The test sends its 5 uploads in parallel and orders the jobs by `created_at`. Two
uploads created microseconds apart can reach the Redis queue in the opposite order,
because `created_at` is set before the request commits and calls `send_task`. The
worker log shows the jobs ran strictly one at a time, in queue order, so the platform
behaves correctly. Proposed fix (not applied): check the one-at-a-time property on
jobs sorted by `started_at`, or space the uploads out.

## See also
- [Worker pipeline](worker-pipeline.md)
- [Usage statistics](usage-statistics.md)
- [Deployment](deployment.md)
- [Repo docs](../sources/repo-docs.md)
