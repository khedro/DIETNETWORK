---
title: specifications.docx — implementation status
type: analysis
sources: [code]
updated: 2026-10-01
---

# specifications.docx: what's done, what isn't

Status of each item in [specifications.docx](../../specifications.docx) (team spec,
in French; raw source, immutable), checked against the `webPlatform` working tree on
2026-10-01. ✅ done · 🟡 partial / differs from spec · ❌ not done.

## Flux utilisateur (user flow)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Account tied to an email address | ✅ | Signup with email verification, argon2id, CAPTCHA (`backend/app/routers/auth.py`) |
| Upload VCF, PLINK, bgen (?) | ✅ | `.vcf/.vcf.gz`, `.bed+.bim+.fam`, `.bgen+.sample` ([uploads.py](../../backend/app/routers/uploads.py)) |
| Download a zip of final results | ✅ | `GET /jobs/{id}/download` ([jobs.py](../../backend/app/routers/jobs.py)). Contents differ from the spec, see below |
| Keep data 30 days (results only) | 🟡 | Raw deleted right after **success**. A **failed** job keeps its raw upload until the 30-day sweep ([tasks.py](../../worker/worker/tasks.py) `_delete_raw` only on success) |
| Improve UI for FCFS | 🟡 | Queue position on the job page, plus a "job started" email. No ETA or global queue view |
| Multiple users | ✅ | Per-user data dirs; jobs only visible to their owner (404 otherwise) |
| Resources: max 1 GB per user | 🟡 | 1 GB is per **upload** (combined files), not per user. No per-user quota or limit on concurrent jobs |
| Resources: use the Diet Network .bim for extraction | ✅ | Pre-flight `--extract dietnet_snps.txt`; `dummy.bim` for allele checks |
| Queue jobs when several users submit | ✅ | Celery/Redis FCFS queue, `CELERY_WORKER_CONCURRENCY` |
| Simultaneous uploads (not handled, 50 GB?) | ✅ as decided | Not handled by design. Only downloads are capped (`MAX_CONCURRENT_DOWNLOADS`) |

## Traitement des données (processing)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Input VCF or PLINK on GRCh38 | ✅ | Plus bgen. GRCh38 is stated in the UI but cannot be verified |
| Extract genotypes in the Diet Network overlap | ✅ | `infer.sh` + pre-flight overlap check (≥ 1,000 SNPs) |
| *Camille:* rebuild the ID column from chr+pos | ❌ | Only **detected**: `detect_id_labeling_mismatch` tells the user to relabel and re-upload. IDs are never rewritten automatically |
| Handle allele flips | 🟡 | Detected and the job **rejected** above 5% (`check_allele_harmonization`). Not corrected |
| Handle allele mismatches | 🟡 | Counted, but the `mismatched` class (non-complementary alleles) is **not** counted toward the 5% threshold; those SNPs pass through silently |
| Per-sample missing rate (reported in the results table) | ❌ | Not computed (no `--missing`/`--mind`). Only per-SNP `--geno 0.1` filtering |
| Statistics against 1KGP | ❌ | None |
| 1KGP Diet Network HDF5 kept on the server | ❌ | Only the Zenodo `DN_SNPS/` + `DN_MODELS/` are baked into the worker image |
| Inference on overlap SNPs | ✅ | `run_infer` → `infer.sh` |
| …report continental performance in the log and per-population confusion matrix | ❌ | Depends on 1KGP data on the server (above) |

## Résultats finaux (final results)

| Spec item | Status | Evidence / gap |
|---|---|---|
| Zip with the result files | ✅ | Zips everything in the results dir: predictions txt, extracted/not-extracted SNP lists, the query HDF5, 15 per-model `.npz` |
| Zip encrypted with a password | ❌ | Plain `zipfile`, no password (would need e.g. `pyzipper`/AES) |
| **Log file:** total SNPs and overlap (by position and alleles?) | 🟡 | Overlap count/total stored in DB and shown in the UI and email. No log file in the zip. Overlap is by **ID** only |
| **Log file:** 1KGP accuracy (continental?) | ❌ | |
| SNP lists in / not in the overlap | ✅ | `*_dietnetsnps_extractedsnps.txt`, `*_notextractedsnps.txt` |
| **Predictions table** (sample, missing rate, continent consensus, population consensus, counts per continent and per population) | ❌ | Current file = `sample, model1..model15, all_models` (e.g. `CEUGBR(12),IBS(3)`). No missing rate, no continent mapping, no consensus columns, no per-population count columns. Not shown in the UI either (`job.predictions` is stored but the job page only shows overlap + download) |
| Consensus threshold 12/15 (80%), NA below | ❌ | Not implemented. Threshold still open in the spec ("?") |

## Figures

| Spec item | Status |
|---|---|
| Confusion matrix on 1KGP | ❌ (needs 1KGP data) |
| Bar plot of 15-model predictions per user sample | ❌ |
| PCA of last hidden layer for 1KGP, projecting user samples | ❌ Needs 1KGP last-layer embeddings. `last_hidden_layer` for user samples is already in the per-model `.npz`. The spec flags checking the effect of missingness first; see [latent representations](../concepts/latent-representations.md) and [missing-SNP handling](../concepts/missing-snp-handling.md) |

## Suggested order for the remaining work

1. **Results table** (consensus, continent mapping, missing rate): output-only, no new data needed. Biggest user-visible gap.
2. **Per-sample missing rate**: `plink --missing` on the overlap set; feeds item 1.
3. **Log file in the zip**: overlap counts, harmonization counts, scale factor, warnings.
4. **Bar plot** of the 15 votes: needs only the predictions.
5. **Password-encrypted zip.**
6. **chr+pos ID rewrite** (turn the current detection into a fix), and decide on `mismatched` alleles.
7. **1KGP reference on the server** → accuracy, confusion matrix, PCA projection. Needs the 1KGP HDF5/embeddings (Zenodo has the training data, per the paper p.1474).

## See also
- [Worker pipeline](../code/worker-pipeline.md)
- [Web platform](../code/web-platform.md)
- [15-model ensemble](../concepts/ensemble.md)
