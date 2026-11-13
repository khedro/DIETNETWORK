# Review: HussinLab/DIETNETWORK#2 — QC step and new outputs for the inference pipeline

Reviewed commits: `d23ff98`, `f553921` (branch `webPlatform_inference`, based on
`webPlatform@353e38b`). Tested 2026-11-13 by running `Dietnet_inference/infer.sh`
from this branch end to end in the existing worker image (+ scikit-learn),
on genotypes taken from the Zenodo 1KGP hdf5 (true labels known).

## Test results

| Case | Input | Result |
|---|---|---|
| full | 40 1KGP samples, all SNPs, panel allele order, 5x3 | PASS — exit 0, 159 s solo; QC continent acc 99.8%; 37/40 population calls correct, 3 `None`; all 7 outputs + plots look right |
| low | 8 samples, 300 SNPs | PASS — QC stops the job (94.1% < 95%), exit 1. Leaves 521 MB `1KGP_RESULTS/` behind |
| numeric | 8 samples, numeric IIDs | FAIL — `hidden_layer_pca.py` crashes (`merge on str and int64`), no PCA plots, but **infer.sh exits 0** |
| minorA1 | same genotypes, PLINK default A1 (minor) | FAIL (silent) — overlap 173,755 vs 229,979: 24% of SNPs dropped |
| folds2x1 | full, 2 folds x 1 rep | FAIL — every sample `None` (thresholds 12/14 hard-coded for 15 models) |
| worker call | 5 args, as `worker/worker/pipeline.py:run_infer` does | FAIL — `seq: invalid ... ''`, exits 1 with "Exit." (looks like a QC failure); no `*_dietnet_predictions.txt` |

## Findings (most severe first)

1. **Breaks the web platform.** `infer.sh` now takes 7 args and writes `<name>_predictions.txt`;
   `worker/worker/pipeline.py:run_infer` passes 5 and reads `<name>_dietnet_predictions.txt`
   (columns `samples, model1..15`). Every web job would fail. Needs a matching worker change
   (and `build_results_table` / tests) in the same PR.
2. **Deployment missing inputs.** QC needs `1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5`,
   `1KGP/..._parition.npz` and `1KGP/1000G.2322samples.labels.txt`. None is fetched by
   `ops/scripts/fetch_zenodo_models.sh`; the partition and labels files are not in the Zenodo
   record at all (the hdf5 is in `Dietnet_training.tar.gz` as `1KGP_dataset.hdf5`). The
   partition must be the one used at training, or the QC accuracy uses training samples.
3. **scikit-learn is not in `dietnet_infer_python3115_requirements.txt`**; `hidden_layer_pca.py`
   imports it — ImportError in the worker image.
4. **SNP-ID rewrite depends on A1/A2 order** (`awk ... $6:$5`). PLINK's default makes A1 the
   minor allele, so any SNP where alt is the major allele gets `chr:pos:alt:ref` and silently
   falls out of the overlap (24% here). Monomorphic sites (allele `0`) are also lost (1,571 of
   ~230k with 8 samples). Previously IDs were left alone, and the worker already relabels and
   harmonises IDs before calling infer.sh — this step undoes that work.
5. **Mutates the user's input** — renames `<prefix>.bim` to `<prefix>_original.bim` and
   overwrites it. A re-run on the same files overwrites the true original. Write the rewritten
   bim to the work dir instead.
6. **Vote thresholds hard-coded** (`--pop-threshold 12 --continent-threshold 14`) while folds/reps
   are parameters — with fewer models nothing reaches consensus. Derive from `nb_folds*nb_reps`.
7. **Failures exit 0.** No `set -e`/exit checks: the numeric-IID crash still prints "completed".
   Sample IDs must be read as strings (`dtype={'Samples': str}` / `dtype=str` for `.imiss`).
8. **Shared fixed dir `1KGP_RESULTS`** in cwd: concurrent runs in one cwd collide; not removed on
   the QC-fail path (521 MB per failed job).
9. **1KGP is inferred twice** (test folds for QC, then all 2322 samples for PCA) = 30 extra model
   passes. Infer all samples once and slice the test indices for accuracy.
10. Minor: `#!/bin/bash` shebang in two Python files; label/colour tables duplicated instead of
    importing `population_config.py`; `create_1kgp_hdf5.py` opens the hdf5 twice and its
    `--output_name` flag only works through argparse abbreviation of `--out`; bar plot
    `set_xticks([0, n])` adds an empty column; per-bar `ax.bar` loop is O(samples x models) calls
    (slow for large cohorts); `MPLCONFIGDIR` warning in the container.

## What works well

QC idea and accuracy computation are sound; `InferenceDataset` partition support is clean and
well-documented; outputs (summary, per-model tables, missingness, bar plots, hidden-layer PCA)
are correct and the plots are clear.

## Reproduce

Data dir layout expected under `/files`: `DN_MODELS/`, `DN_SNPS/` (Zenodo `Dietnet_inference.tar.gz`),
`1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5` (= `Dietnet_training/1KGP_dataset.hdf5`).
`mk_partition.py` regenerates a balanced 5-fold partition (NOT the training one) and the labels file (copy `Dietnet_train_and_evaluate/partition_data.py` next to it first).

```
docker build -t dietnet-pr2-review:test tests/pr2_inference_qc      # worker image + scikit-learn
docker run ... python mk_partition.py; python mk_data.py; bash mk_beds.sh
docker run ... bash run_case.sh <case> <dataset> <folds> <reps>     # mounts /code /files /data /runs
```
