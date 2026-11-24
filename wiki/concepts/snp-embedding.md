---
title: SNP embedding (per-population genotype frequencies)
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# SNP embedding

Each SNP is described by a vector of **genotype frequencies per population in the
training set**: for each of the 24 populations, the fraction of individuals with
genotype 0, 1 and 2. That gives 72 numbers per SNP. The auxiliary network maps this
vector to the SNP's fat-layer weights (Paper p.1464, "defined as genotype
frequencies per population in the training set").

## Implementation

- [generate_embedding.py:125-143](../../Dietnet_train_and_evaluate/generate_embedding.py#L125-L143)
  (`compute_fold_embedding`): column `3*c + g` = count of genotype `g` in class `c`,
  divided by the class size. Missing genotypes (-1) match no column, so they are
  effectively left out of the numerator but still counted in the denominator.
- One embedding per fold, computed from **training samples only** by default
  (`--include-valid`, `--only-valid`, `--only-test` change this). Saved as `emb` with
  shape `(folds, n_snps, 72)`.
- At load time the embedding is L2-normalized per column over the SNP axis
  ([model.py:293-294](../../Dietnet_train_and_evaluate/helpers/model.py#L293-L294)); the same
  happens in [inference.py:141-143](../../Dietnet_inference/inference.py#L141-L143).
- Released artifact: `DN_MODELS/snps_emb_model{fold}.npz` (one per fold, shared by
  that fold's 3 repeats), fetched from Zenodo.

## Why fold-specific

Computing it on each fold's training set avoids leaking label information from
validation/test samples into the model parameters. This is why the README says to
partition *before* building the embedding.

## See also
- [Diet Network architecture](diet-network-architecture.md)
- [Training pipeline](../code/training-pipeline.md)
