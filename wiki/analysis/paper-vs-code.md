---
title: Paper vs code — agreements, gaps, contradictions
type: analysis
sources: [paper, code]
updated: 2026-09-28
---

# Paper vs code

Where the implementation matches the paper's theory, and where it does not. The paper
is immutable, so this page records discrepancies; it does not resolve them. Update it
on every ingest.

## Confirmed matches

| Paper says | Code | Status |
|---|---|---|
| Aux net generates fat-layer weights from a per-SNP embedding (p.1463) | `DietNetwork.forward`, `AuxiliaryNetwork` | ✅ |
| Embedding = per-population genotype frequencies, training set only (p.1464) | `compute_fold_embedding` | ✅ |
| Standardize with training mean/SD (p.1464) | `compute_input_features_statistics.py`, `du.normalize` | ✅ |
| 60/20/20 population-balanced split, 5 folds (p.1463–1464) | `partition_data.py` defaults (5 folds, 0.75 train/valid) | ✅ arithmetic matches; balance not verified |
| 15 models = 5 folds × 3 repeats (p.1463) | `infer.sh` loop, `weights_model{1-5}_{1-3}.pt` | ✅ |
| 24 populations, CEUGBR and STUITU merged (p.1463) | `dn_label_order`, `NB_POP=24` | ✅ |
| Remaining SNPs rescaled when SNPs are missing (p.1464) | `scale = total/found` in `infer.sh` | ✅ exact formula only in code |
| Last hidden layer (100 neurons) as the representation (p.1464) | `last_hidden_layer` saved per model | ✅ |
| CPU inference is feasible (p.1464) | platform runs CPU-only | ✅ |
| Input dropout regularization (p.1466) | `MainNetwork.input_dropout` | ✅ mechanism; the 0.995 value is in no committed config |

## Gaps (in the paper, not found in the repo)

Caveat: shell access was unavailable while this page was written, so the repo could not
be listed exhaustively. Files were read by known paths. Re-check these with a lint pass.

- **Training config YAML** with the published hyperparameters (input dropout 0.995,
  LRs, epochs, patience).
- **Checkpoint → release export**: training writes 3-D `emb` and
  `means_by_fold`/`sd_by_fold`; inference expects per-fold 2-D `emb` and `mean`/`std`.
  **Does not affect the web platform**, which only consumes the released Zenodo files
  (already in inference format) and never trains. It matters only if someone retrains
  and wants to serve the new weights. They would then have to write this export step
  and replace `DN_MODELS/` in the worker image.
- **Attribution scripts** (Captum runs, corruption curves, baselines, global/pairwise
  aggregation). Only the `DietNetworkAttr` wrapper was found.
- **Latent-space PCA** and the F_ST (VCFtools) comparison scripts.
- **Harmonized SNP set construction** (strand alignment, TOPMed filter, LD pruning,
  ShapeIT5). Only the resulting `dietnet_snps.txt` is shipped, via Zenodo.
- **Benchmarks** (PCA+RF, Rye).

## Docs vs code

- README `infer.sh` usage `<plink_prefix> <output_prefix> <plink_path> <dietnet_path>`
  is **wrong**. The script takes 5 arguments:
  `<plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>`.
  **This is upstream's error, not the fork's**, verified in git on 2026-09-28: the usage
  line came from commit `d69d184` (Camille Rochefort-Boulanger, 2026-02-25, "Revise README
  for inference"). `infer.sh` has not changed since then, and `origin/main` has the
  same mismatch. The fork's only README change (`96e3668`) added the web-platform
  note. **Fixed in the fork's README on 2026-09-28**: the correct 5-argument usage is
  now documented, with a correction note naming the upstream commit. `infer.sh` itself
  was not changed. Still worth reporting upstream.
- README cites the 2025 bioRxiv preprint. The paper of record is AJHG 113:1461–1477 (2026).
- README says input files are "tab-separated", but `inference_dataset.py` splits PLINK
  `.raw` lines on **spaces**. The training `create_dataset.py` was not checked.
- `train.py` header comment lists `learning_rate`; the model reads `lr_aux` and `lr_main`.
- `mainloop_utils.py` Theano helpers reference classes that no longer exist and use
  `n_targets=26`. Dead code.
- **Caddy ports:** [docker-compose.yml:140-142](../../docker-compose.yml#L140-L142) hard-codes
  `8080:80`/`8443:443` in the base file. DEPLOYMENT.md says the base file is used
  unchanged on Arbutus and that only the local-test setup uses 8080/8443. **Intentional
  for now** (2026-09-28): the owner is testing on a local server. **Before a real Arbutus
  deploy, switch these to `80:80`/`443:443`**; otherwise production listens on
  8080/8443 and ACME HTTP-01 on port 80 fails.
- DEPLOYMENT.md says `tasks.py` holds all four pre-flight checks, including upload
  size. `tasks.py` has sample count, overlap and harmonization; upload size is enforced
  elsewhere (backend `MAX_UPLOAD_MB`).
- `ENSEMBLE_WORKERS` is configured, but `infer.sh` runs the 15 models sequentially.

## Theory → platform decisions

The platform turns several paper findings into rules:
- "Don't trust < 1000 SNPs" → hard pre-flight rejection.
- Heavy missingness drifts toward the PUR default ([F_ST](../concepts/fst.md)) → the
  overlap floor matters scientifically, not just technically.
- `--real-ref-alleles` with no automatic allele flipping → allele-harmonization rejection.
- No calibrated uncertainty (p.1473) → stored predictions keep all 15 votes plus the
  `all_models` tally, not one label. How the frontend displays them is unverified.

## See also
- [Publication](../sources/publication.md)
- [Inference pipeline](../code/inference-pipeline.md)
- [Training pipeline](../code/training-pipeline.md)
