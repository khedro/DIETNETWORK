---
title: Worker pipeline and guardrails (worker/)
type: code
sources: [code]
updated: 2026-09-28
---

# Worker pipeline

The Celery worker converts a user's upload to PLINK, runs four pre-flight checks,
calls `infer.sh`, and stores the parsed predictions. Code:
[tasks.py](../../worker/worker/tasks.py) (orchestration) and
[pipeline.py](../../worker/worker/pipeline.py) (each step). As of 2026-09-28 both have
uncommitted changes, and this page reflects the working tree.

## `run_inference_job(job_id)` flow

1. Mark the job `running`; send a "job started" email. An email failure here is
   logged and does not fail the job.
2. **Convert to PLINK with `--geno 0.1` QC and `--real-ref-alleles`**:
   - VCF → `plink --vcf` ([pipeline.py:38-66](../../worker/worker/pipeline.py#L38-L66))
   - bgen + .sample → `plink2 --bgen ... ref-first` ([pipeline.py:69-88](../../worker/worker/pipeline.py#L69-L88))
   - PLINK → re-written through the same filter (`requalify_plink`)
3. **Guardrails** (each raises a user-safe `PipelineError`):

| Check | Default | Code |
|---|---|---|
| Upload size | `MAX_UPLOAD_MB` = 1024 | backend (upload intake) |
| Sample count | `MAX_SAMPLES` = 10,000 | `count_samples` |
| SNP overlap | `MIN_RELIABLE_SNP_OVERLAP` = 1,000 | `check_snp_overlap` + `detect_id_labeling_mismatch` hint |
| Allele harmonization | `MAX_ALLELE_MISMATCH_FRACTION` = 0.05 | `check_allele_harmonization` vs `DN_SNPS/dummy.bim` |

4. `run_infer` calls `infer.sh` with the real argument order, `cwd` = results dir and
   a relative output name. It fails if no predictions file appears.
5. Parse predictions into JSON; set `snp_overlap_count/total` and `is_reliable`; store.
6. Delete the raw upload if `DELETE_RAW_AFTER_SUCCESS` (default on); send the
   completion email (no genetic data in the email).
7. On any exception: status `failed`, user sees only the `PipelineError` text or a
   generic message; traceback goes to logs.

## Design notes worth knowing

- **Why the pre-flight overlap check duplicates `infer.sh` step 1:** it rejects hopeless
  jobs in seconds instead of after the 15-model run. PLINK exits non-zero on exactly
  zero overlap, which is caught and treated as a 0 count ([pipeline.py:152-165](../../worker/worker/pipeline.py#L152-L165)).
- **ID-labeling hint:** compares `chrom:pos` sets. If position overlap ≥ 1000 and
  more than twice the ID overlap, the user is told to relabel SNP IDs.
- **Harmonization classes:** matched, swapped (A1/A2 reversed), flipped (complement
  strand), ambiguous (A/T or C/G, where swap and flip look identical), mismatched. Only
  swapped + flipped + ambiguous count toward the 5% threshold.
- **Why `--real-ref-alleles` on conversion:** without it PLINK 1.9 makes the sample's
  major allele A2, producing spurious "swaps" for well-harmonized data.
- `_run` logs stderr even on exit 0, because `infer.sh` hides Python failures.
- `ENSEMBLE_WORKERS` exists in [config.py:66](../../worker/worker/config.py#L66), but
  `run_infer` runs `infer.sh` sequentially; no use of it was seen in the files read.

## Retention

[cleanup.py](../../worker/worker/cleanup.py): a daily Celery beat task purges jobs
whose DB `created_at` is older than `RETENTION_DAYS` (30). It deletes raw and results
directories, nulls stored predictions, and sets `purged_at`. It uses DB time, not file
mtime. A systemd-timer alternative is in `ops/`.

## Tests

`worker/tests/test_pipeline.py` (not read in this ingest).

## See also
- [Inference pipeline](inference-pipeline.md)
- [Web platform](web-platform.md)
- [Harmonized SNP set](../concepts/harmonized-snp-set.md)
