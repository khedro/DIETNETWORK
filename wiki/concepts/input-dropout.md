---
title: Input dropout
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Input dropout

During training, randomly zero out a very large fraction of each sample's input
genotypes. The paper found **0.995** best: on average only ~1,150 of 229,986 SNPs
are seen per sample per step (Paper p.1466, Fig. 1A). It is the main reason the
model generalizes to datasets with different SNP coverage.

## What it buys (paper)

- Higher test accuracy on complete data than rates 0, 0.9 or 0.999 (Fig. 1A).
- Accuracy holds up to ~99% simulated missingness (Fig. 1A).
- More stable predictions across increasing missingness (Fig. S6), more consistent
  latent representations (Fig. S9), less variation across random initializations
  (Fig. S10) (Paper p.1468, 1472).
- Rationale: the model cannot lean on a small fixed subset of very informative SNPs
  (Paper p.1472).

## Implementation

- `nn.Dropout(config['input_dropout'])` applied to the input before the fat layer
  ([model.py:118](../../Dietnet_train_and_evaluate/helpers/model.py#L118),
  [model.py:215](../../Dietnet_train_and_evaluate/helpers/model.py#L215)).
- Inputs have already been standardized, so a dropped input equals 0, which is the
  training-set mean — the same value a missing genotype takes. Dropout and
  missingness therefore look identical to the network. This is the link to
  [missing-SNP handling](missing-snp-handling.md).
- Standard PyTorch dropout rescales kept inputs by 1/(1-p) during training (×200 at
  p = 0.995). The inference-time scale factor for missing SNPs mirrors that idea.
- Hyperparameter lives in the YAML config passed to `train.py --config`. No config
  file was found in the repo (see [paper vs code](../analysis/paper-vs-code.md)).

## See also
- [Missing-SNP handling](missing-snp-handling.md)
- [Diet Network architecture](diet-network-architecture.md)
