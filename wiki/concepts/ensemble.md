---
title: 15-model ensemble
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# 15-model ensemble

Released predictions come from 15 models: 5 cross-validation folds × 3 repeats
with different random seeds (Paper p.1463, 1466). There is no averaging of
probabilities. Each model votes, and the output lists all 15 labels plus a tally.

## Why 15 labels instead of one

The paper uses disagreement between models as a rough uncertainty signal, since the
model has no built-in confidence estimate (Paper p.1473). Figures 1C/D, 2A/B and 3A
plot all 15 labels per individual. Mixed votes flag admixed individuals or people
from unrepresented populations.

## Files

- Weights: `DN_MODELS/weights_model{fold}_{rep}.pt` (15 files).
- Per fold: `snps_emb_model{fold}.npz` and `norm_stats_model{fold}.npz` (5 each).
  The 3 repeats of a fold share an embedding and normalization stats.
- Loop: [infer.sh:107-118](../../Dietnet_inference/infer.sh#L107-L118), sequential.
- Combine: [inference_combine_results.py](../../Dietnet_inference/inference_combine_results.py)
  maps class indices to labels using a hard-coded, alphabetically ordered list of the
  24 populations, renames columns `model1..model15`, and adds `all_models`, e.g.
  `CEUGBR(12),IBS(3)`.

## Class index order

`ACB ASW BEB CDX CEUGBR CHB CHS CLM ESN FIN GIH GWD IBS JPT KHV LWK MSL MXL PEL PJL PUR STUITU TSI YRI`
([inference_combine_results.py:9-13](../../Dietnet_inference/inference_combine_results.py#L9-L13)).
This must match the label encoding used at training time. See [populations](../entities/populations.md).

## See also
- [Inference pipeline](../code/inference-pipeline.md)
- [Latent representations](latent-representations.md)
