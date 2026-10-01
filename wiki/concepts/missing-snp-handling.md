---
title: Missing-SNP handling (mean imputation, standardization, rescaling)
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Missing-SNP handling

A query dataset rarely has all 229,986 training SNPs. The pipeline makes absent
SNPs look like "no information" and boosts the ones that are present, so the
network sees inputs on roughly the same scale as in training (Paper p.1464, Methods S4.4).

## Steps

1. **Fill to the full SNP set.** `infer.sh` merges the query with a one-sample dummy
   PLINK file holding every training SNP (`--merge-mode 5`), then drops the dummy.
   Absent SNPs become missing ([infer.sh:39-59](../../Dietnet_inference/infer.sh#L39-L59)).
2. **Encode missing as -1** in the HDF5 ([inference_dataset.py:79-83](../../Dietnet_inference/inference_dataset.py#L79-L83)).
3. **Mean-impute.** Replace -1 with the training-fold mean of that SNP
   ([inference.py:188-191](../../Dietnet_inference/inference.py#L188-L191);
   training: [dataset_utils.py:184-191](../../Dietnet_train_and_evaluate/helpers/dataset_utils.py#L184-L191)).
4. **Standardize** with training-fold mean and SD. Imputed values become exactly 0.
5. **Rescale** all values by `scale = n_training_snps / n_overlapping_snps`
   ([infer.sh:62](../../Dietnet_inference/infer.sh#L62),
   [inference.py:197](../../Dietnet_inference/inference.py#L197)). Zeros stay zero, so
   only observed SNPs are boosted. This keeps the fat-layer pre-activation at a similar
   magnitude, the same way dropout's 1/(1-p) rescaling does in training.

## Evidence it works

| Dataset | Missing SNPs | Outcome |
|---|---|---|
| AoU | 25,319 (~11%) | Continental ancestry preserved (Paper p.1467) |
| CaG Omni | 59,448 (~26%) | FC profiles match complete-data GSA results (Fig. 2B) |
| CaG Axiom | 174,736 (~76%) | Same as above |
| Simulated | up to 99% | Changes stay within continent until ~99% (Fig. 2C, S5) |

Admixed groups (Haitians, MHIB Africans) and populations without a close 1KGP match
(French Canadians) are the least stable (Paper p.1467).

## Failure mode: drift toward PUR

When nearly everything is missing, the input approaches the all-zero "genotype
average" vector, and the models tend to predict **PUR**, which behaves as a default
class under ambiguity (Paper p.1473, Figs. S5, S12). See [F_ST](fst.md) for why.

## Platform guardrail

The web worker refuses jobs with fewer than 1,000 overlapping SNPs, the threshold
that `infer.sh` itself prints as a warning ([infer.sh:131](../../Dietnet_inference/infer.sh#L131);
[worker pipeline](../code/worker-pipeline.md)).

## See also
- [Input dropout](input-dropout.md)
- [Harmonized SNP set](harmonized-snp-set.md)
- [Inference pipeline](../code/inference-pipeline.md)
