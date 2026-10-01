---
title: Inference pipeline (Dietnet_inference/)
type: code
sources: [code, paper]
updated: 2026-09-28
---

# Inference pipeline

[Dietnet_inference/](../../Dietnet_inference/) turns a GRCh38 PLINK dataset into
15 ancestry predictions per sample. It is a bash driver around PLINK 1.9 and three
Python scripts. Python 3.11.5, pinned in `dietnet_infer_python3115_requirements.txt`.

## Invocation

```
bash infer.sh <plink_path> <dietnet_code_path> <dietnet_files_path> <plink_test_prefix> <output_name>
```

This is the **real** order, from the script's own argument parsing
([infer.sh:6-10](../../Dietnet_inference/infer.sh#L6-L10)). The upstream README
showed a wrong 4-argument form. The fork's README was corrected on 2026-09-28
([paper vs code](../analysis/paper-vs-code.md#docs-vs-code)).
`dietnet_files_path` is the Zenodo download containing `DN_SNPS/` and `DN_MODELS/`.

## Stages

| # | Stage | Where | Output |
|---|---|---|---|
| 1 | Extract training SNPs from the query | [infer.sh:20-31](../../Dietnet_inference/infer.sh#L20-L31) | exits if no overlap |
| 2 | List found / not-found SNPs | [infer.sh:34-37](../../Dietnet_inference/infer.sh#L34-L37) | `*_extractedsnps.txt`, `*_notextractedsnps.txt` |
| 3 | Fill absent SNPs as missing by merging with `DN_SNPS/dummy` | [infer.sh:43-51](../../Dietnet_inference/infer.sh#L43-L51) | |
| 4 | Additive recode (`--recode A`), drop dummy | [infer.sh:54-59](../../Dietnet_inference/infer.sh#L54-L59) | `.raw` |
| 5 | Scale = total SNPs / found SNPs | [infer.sh:62](../../Dietnet_inference/infer.sh#L62) | |
| 6 | `.raw` → HDF5 (`inputs` int8, `snp_names`, `samples`, `scale`) | [inference_dataset.py](../../Dietnet_inference/inference_dataset.py) | `<out>.hdf5` |
| 7 | 15 × `inference.py` | [infer.sh:107-118](../../Dietnet_inference/infer.sh#L107-L118) | `<out>_DIETNET_RESULTS_BY_MODEL/*_model{f}_{r}_infered.npz` |
| 8 | Combine votes | [inference_combine_results.py](../../Dietnet_inference/inference_combine_results.py) | `<out>_dietnet_predictions.txt` |
| 9 | Print SNP overlap and the "< 1000 SNPs: don't trust" warning | [infer.sh:130-131](../../Dietnet_inference/infer.sh#L130-L131) | stdout |

## inference.py in one paragraph

Loads the fold's SNP embedding, normalizes it, runs the auxiliary net once to get the
fat-layer weights, and builds a plain MLP from the checkpoint. Then, per batch:
mean-impute missing values, standardize with `norm_stats` (`mean`, `std`), multiply
by `scale`, forward pass. Saves `preds` (argmax), `scores` (softmax, 24), and
`last_hidden_layer` (100) per sample ([inference.py:110-225](../../Dietnet_inference/inference.py#L110-L225)).
`NB_POP = 24` is hard-coded. Runs on CPU if CUDA is absent.

## Gotchas

- **Silent failures.** `infer.sh` never checks the Python steps' exit codes. It can
  print "completed" and exit 0 with no predictions. The platform works around this
  ([worker pipeline](worker-pipeline.md)).
- **`output_name` must be relative.** It is used twice in a path
  (`${output_dir}/${output_name}_model...`), so an absolute prefix creates a doubled,
  broken path ([pipeline.py:292-328](../../worker/worker/pipeline.py#L292-L328)).
- **Writes into the working directory**, e.g. `sample_order.txt`. Parallel runs in the
  same directory would collide.
- **`--real-ref-alleles`** everywhere: allele order must already match the panel
  ([harmonized SNP set](../concepts/harmonized-snp-set.md)).
- SNP IDs must be `chr<c>:<pos>:<ref>:<alt>`.
- `inference_dataset.py` parses `.raw` lines by splitting on single spaces, and treats
  `./.` and `NA` as missing. PLINK's `.raw` uses `NA`.

## See also
- [Missing-SNP handling](../concepts/missing-snp-handling.md)
- [15-model ensemble](../concepts/ensemble.md)
- [Diet Network architecture](../concepts/diet-network-architecture.md)
