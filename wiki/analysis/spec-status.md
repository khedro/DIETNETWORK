---
title: specifications.docx — implementation status
type: analysis
sources: [code]
updated: 2026-10-30
---

# specifications.docx: what's done, what isn't

Status of each item in [specifications.docx](../../specifications.docx) (team spec,
in French; raw source, immutable), rechecked against `webPlatform` at `e54b406` on
2026-10-30 (first checked 2026-10-01). ✅ done · 🟡 partial / differs from spec · ❌ not done.
Items marked *(since 10-01)* changed status in this pass.

## Flux utilisateur (user flow)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Account tied to an email address | ✅ | Signup with email verification, argon2id, CAPTCHA (`backend/app/routers/auth.py`) |
| Upload VCF, PLINK, bgen (?) | ✅ | `.vcf/.vcf.gz`, `.bed+.bim+.fam`, `.bgen+.sample` ([uploads.py](../../backend/app/routers/uploads.py)); the homepage lists all three since `e54b406` |
| Download a zip of final results | ✅ | `POST /jobs/{id}/download` with a password ([jobs.py](../../backend/app/routers/jobs.py)) |
| Keep data 30 days (results only) | 🟡 | Raw deleted right after **success**. A **failed** job keeps its raw upload until the 30-day sweep ([tasks.py](../../worker/worker/tasks.py) `_delete_raw` only on success) |
| Improve UI for FCFS | 🟡 | Queue position on the job page, plus "job started" / "ready" / "failed" emails. No ETA or global queue view |
| Multiple users | ✅ | Per-user data dirs; jobs only visible to their owner (404 otherwise) |
| Resources: max 1 GB per user | 🟡 | 1 GB is per **upload** (combined files), not a per-user quota. *(since 10-01)* Each user is now limited to one queued or running job (`409`), which caps per-user disk use in practice |
| Resources: use the Diet Network .bim for extraction | ✅ | Pre-flight `--extract dietnet_snps.txt`; `dummy.bim` for relabelling and allele checks |
| Queue jobs when several users submit | ✅ | Celery/Redis FCFS queue, up to `CELERY_WORKER_CONCURRENCY` = 9 at once |
| Simultaneous uploads (not handled, 50 GB?) | ✅ as decided | Not handled by design. Only downloads are capped (`MAX_CONCURRENT_DOWNLOADS`) |

## Traitement des données (processing)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Input VCF or PLINK on GRCh38 | ✅ | Plus bgen. GRCh38 is stated in the UI but cannot be verified |
| Extract genotypes in the Diet Network overlap | ✅ | `infer.sh` + pre-flight overlap check (≥ 1,000 SNPs) |
| *Camille:* rebuild the ID column from chr+pos | ✅ *(since 10-01)* | `relabel_snp_ids` rewrites every ID to the panel's `chr:pos:ref:alt` by chromosome + position before the checks ([worker pipeline](../code/worker-pipeline.md)) |
| Handle allele flips | 🟡 | Detected and the job **rejected** above 5% (`check_allele_harmonization`). Not corrected |
| Handle allele mismatches | 🟡 | Counted and reported in the job log, but the `mismatched` class (non-complementary alleles) is **not** counted toward the 5% threshold; those SNPs pass through |
| Per-sample missing rate (reported in the results table) | ✅ *(since 10-01)* | `plink --missing` over the overlapping SNPs (`compute_sample_missing_rates`); a column of the results table |
| Statistics against 1KGP | ❌ | None |
| 1KGP Diet Network HDF5 kept on the server | ❌ | Only the Zenodo `DN_SNPS/` + `DN_MODELS/` are baked into the worker image |
| Inference on overlap SNPs | ✅ | `run_infer` → `infer.sh` |
| …report continental performance in the log and per-population confusion matrix | ❌ | Depends on 1KGP data on the server (above) |

## Résultats finaux (final results)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Zip with the result files | ✅ | Everything in `results/`: results table, job log, predictions txt, extracted/not-extracted SNP lists, the query HDF5, 15 per-model `.npz` |
| Zip encrypted with a password | ✅ *(since 10-01)* | AES-256 via pyzipper, password chosen at download and never stored ([results_zip.py](../../backend/app/results_zip.py)). Opens in 7-Zip, not Windows Explorer |
| **Log file:** total SNPs and overlap (by position and alleles?) | ✅ *(since 10-01)* | `result_job_log.txt`: SNPs after QC, overlap by position, by ID and by alleles, relabelling and harmonization counts, `infer.sh` output |
| **Log file:** 1KGP accuracy (continental?) | ❌ | Needs 1KGP data on the server |
| SNP lists in / not in the overlap | ✅ | `*_dietnetsnps_extractedsnps.txt`, `*_notextractedsnps.txt` |
| **Predictions table** (sample, missing rate, continent consensus, population consensus, counts per continent and per population) | ✅ *(since 10-01)* | `result_results_table.tsv`, columns in the spec's order; same rows in `GET /jobs/{id}`. **Not shown in the UI**: the job page shows overlap and the download only |
| Consensus threshold 12/15 (80%), NA below | ✅ *(since 10-01)* | `CONSENSUS_THRESHOLD` = 12, configurable; `NA` below |

## Figures

| Spec item | Status |
|---|---|
| Confusion matrix on 1KGP | ❌ (needs 1KGP data) |
| Bar plot of 15-model predictions per user sample | ❌ |
| PCA of last hidden layer for 1KGP, projecting user samples | ❌ Needs 1KGP last-layer embeddings. `last_hidden_layer` for user samples is already in the per-model `.npz`. The spec flags checking the effect of missingness first; see [latent representations](../concepts/latent-representations.md) and [missing-SNP handling](../concepts/missing-snp-handling.md) |

## Outside the spec, added since

- [Usage statistics](../code/usage-statistics.md) for grant and Alliance resource
  requests (team request, not in specifications.docx).

## Suggested order for the remaining work

1. **Show the results table on the job page.** The data is already in `GET /jobs/{id}`.
2. **Bar plot** of the 15 votes per sample: needs only the predictions.
3. **Delete the raw upload of failed jobs** right away, to match the 30-day spec.
4. Decide on **`mismatched` alleles** and whether to correct flips instead of rejecting.
5. **1KGP reference on the server** → accuracy in the log, confusion matrix, PCA
   projection. Needs the 1KGP HDF5/embeddings (Zenodo has the training data, per the
   paper p.1474).

## See also
- [Worker pipeline](../code/worker-pipeline.md)
- [Web platform](../code/web-platform.md)
- [Usage statistics](../code/usage-statistics.md)
- [15-model ensemble](../concepts/ensemble.md)
