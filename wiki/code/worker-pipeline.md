---
title: Worker pipeline and guardrails (worker/)
type: code
sources: [code]
updated: 2026-10-30
---

# Worker pipeline

The Celery worker converts a user's upload to PLINK, rewrites SNP IDs by position,
runs the pre-flight checks, calls `infer.sh`, and turns the 15 votes into the results
table and job log. Code: [tasks.py](../../worker/worker/tasks.py) (orchestration) and
[pipeline.py](../../worker/worker/pipeline.py) (each step), as committed in `e54b406`.

For where this sits in the container topology — `infer.sh` runs as a plain
`subprocess` child of the `worker` container itself, not a separate service or a
Celery call — see the full diagram in [Web platform](web-platform.md#topology).

## `run_inference_job(job_id)` flow

1. Mark the job `running`; send a "job started" email. An email failure here is
   logged and does not fail the job.
2. **Convert to PLINK with `--geno 0.1` QC and `--real-ref-alleles`**:
   - VCF → `plink --vcf` ([pipeline.py:40-68](../../worker/worker/pipeline.py#L40-L68))
   - bgen + .sample → `plink2 --bgen ... ref-first` ([pipeline.py:71-90](../../worker/worker/pipeline.py#L71-L90))
   - PLINK → re-written through the same filter (`requalify_plink`, [pipeline.py:93](../../worker/worker/pipeline.py#L93))
3. **Sample count** (`count_samples`): reject above `MAX_SAMPLES`.
4. **Rewrite SNP IDs by chromosome + position** (`relabel_snp_ids`,
   [pipeline.py:309](../../worker/worker/pipeline.py#L309)) to the panel's
   `chr:pos:ref:alt` form, using `DN_SNPS/dummy.bim`. rsID-labelled or `chr`-less
   uploads now overlap without the user relabelling them. Counts (relabelled, already
   matching, no position match, allele mismatch, duplicates) go into the job log.
5. **Guardrails** (each raises a user-safe `PipelineError`):

| Check | Default | Code |
|---|---|---|
| Upload size | `MAX_UPLOAD_MB` = 1024 | backend (upload intake) |
| One active job per user | queued or running → `409` | backend ([uploads.py:92](../../backend/app/routers/uploads.py#L92)) |
| Sample count | `MAX_SAMPLES` = 10,000 | `count_samples` |
| SNP overlap | `MIN_RELIABLE_SNP_OVERLAP` = 1,000 | `check_snp_overlap` + `detect_id_labeling_mismatch` hint |
| Allele harmonization | `MAX_ALLELE_MISMATCH_FRACTION` = 0.05 | `check_allele_harmonization` vs `DN_SNPS/dummy.bim` |

6. **Per-sample missing rate** over the overlapping SNPs
   (`compute_sample_missing_rates`, `plink --missing`, [pipeline.py:389](../../worker/worker/pipeline.py#L389)).
7. `run_infer` calls `infer.sh` with the real argument order, `cwd` = results dir and
   a relative output name. It fails if no predictions file appears.
8. **Results table** (`build_results_table`, [pipeline.py:476](../../worker/worker/pipeline.py#L476)):
   per sample, the missing rate, a continent and a population consensus (the label with
   ≥ `CONSENSUS_THRESHOLD` = 12 of 15 votes, else `NA`), and vote counts for the 5
   continents and 24 populations. Written to `result_results_table.tsv`; the same rows
   go into `jobs.predictions`.
9. **Job log** (`write_job_log`): sample count, SNP totals, overlap by position / ID /
   alleles, relabelling and harmonization counts, consensus threshold and how many
   samples reached it, and the full `infer.sh` output. Written to `result_job_log.txt`.
10. Set `snp_overlap_count/total`, `is_reliable` and **`sample_count`** on the job row
    ([tasks.py:208](../../worker/worker/tasks.py#L208)); status `done`.
11. Delete the raw upload if `DELETE_RAW_AFTER_SUCCESS` (default on); send the
    completion email (no genetic data in the email).
12. On any exception: status `failed`, user sees only the `PipelineError` text or a
    generic message; traceback goes to logs. `sample_count` is only set on success.

## Design notes worth knowing

- **Why the pre-flight overlap check duplicates `infer.sh` step 1:** it rejects hopeless
  jobs in seconds instead of after the 15-model run. PLINK exits non-zero on exactly
  zero overlap, which is caught and treated as a 0 count ([pipeline.py:162-175](../../worker/worker/pipeline.py#L162-L175)).
- **ID-labeling hint:** only appears when the overlap is still too low after the
  position-based relabel. It then reports how many panel positions matched but had
  different alleles.
- **Harmonization classes:** matched, swapped (A1/A2 reversed), flipped (complement
  strand), ambiguous (A/T or C/G, where swap and flip look identical), mismatched. Only
  swapped + flipped + ambiguous count toward the 5% threshold; `mismatched` is
  counted and logged but does not reject the job.
- **Why `--real-ref-alleles` on conversion:** without it PLINK 1.9 makes the sample's
  major allele A2, producing spurious "swaps" for well-harmonized data.
- `_run` logs stderr even on exit 0, because `infer.sh` hides Python failures.
- `ENSEMBLE_WORKERS` exists in [config.py:71](../../worker/worker/config.py#L71), but
  `run_infer` runs `infer.sh` sequentially; it is not used.
- Up to `CELERY_WORKER_CONCURRENCY` = 9 jobs run at once, one per Celery process.

## Retention

[cleanup.py](../../worker/worker/cleanup.py): a daily Celery beat task (03:00 UTC, on
the `maintenance` queue) purges jobs whose DB `created_at` is older than
`RETENTION_DAYS` (30). It deletes raw and results directories, clears stored
predictions, and sets `purged_at`. It uses DB time, not file mtime. A systemd-timer
alternative is in `ops/`.

- The job **row is kept**, with `status`, `sample_count` and `snp_overlap_*`, so
  [usage statistics](usage-statistics.md) stay complete after the purge.
- `job.predictions = None` on the SQLAlchemy `JSON` column stores a JSON `null`, not
  SQL `NULL`. Queries checking for purged predictions need
  `coalesce(predictions::text, 'null') = 'null'`, not `predictions IS NULL`.

## Tests

Unit tests in [worker/tests/test_pipeline.py](../../worker/tests/test_pipeline.py)
(23 tests) and the end-to-end suite are described in [Testing](testing.md).

## See also
- [Inference pipeline](inference-pipeline.md)
- [Web platform](web-platform.md)
- [Usage statistics](usage-statistics.md)
- [Testing](testing.md)
- [Harmonized SNP set](../concepts/harmonized-snp-set.md)
- [15-model ensemble](../concepts/ensemble.md)
