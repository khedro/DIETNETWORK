---
title: Feature attribution (interpretability framework)
type: concept
sources: [paper, code]
updated: 2026-09-28
---

# Feature attribution

Gradient-based methods that score how much each SNP pushed a model toward each
population. The paper evaluates them with SNP-corruption curves, selects
**DeepLift**, and aggregates the scores into global and pairwise views that it
compares with [F_ST](fst.md) (Paper p.1464–1465, 1468–1471).

## Methods compared (Captum)

Saliency Maps, Integrated Gradients, DeepLift, GradientSHAP. Every method except
Saliency needs a [baseline](attribution-baselines.md). Output: local scores of shape
SNP × population × individual (229,986 × 24 per person), computed on each model's
test set.

## Evaluating an attribution method: corruption AUCs

Rank one individual's SNPs by attribution for the predicted class, then corrupt more
and more of them and track accuracy (Paper p.1465):

- **A_ord**: corrupt most important first. Lower is better (accuracy should collapse fast).
- **A_rev**: corrupt least important first. Higher is better.
- **A_ran**: random order, reference = 0.481 ± 0.025.

Corruption strategies: shuffle across the test set (main one), 1NN imputation,
genotype-average, reference, highest-entropy sample.

**Table 1 (shuffle corruption, genotype-average baseline):**

| Method | A_ord | A_rev |
|---|---|---|
| DeepLift | 0.039 ± 0.008 | 0.877 ± 0.013 |
| GradientSHAP | 0.036 ± 0.006 | 0.878 ± 0.013 |
| Integrated Gradients | 0.036 ± 0.007 | 0.878 ± 0.013 |
| Saliency Maps | 0.201 ± 0.020 | 0.653 ± 0.035 |

DeepLift, GradientSHAP and IG agree strongly (Spearman ≈ 0.88–0.99; top-1% Jaccard
0.45–0.90), so DeepLift was picked as representative (Paper p.1469, Fig. 4B).

## Aggregations

- **Global score per SNP**: for each individual, take the local score for the
  *predicted* class, then average over individuals (Paper p.1465). Averaging proved
  the most robust choice (Methods S4.5).
- **Pairwise score** (true population × target population): average local scores
  over SNPs and over individuals of the true population (Paper p.1465). This produces
  the heatmap in Fig. 5C.

## In the code

- `DietNetworkAttr` wraps the model with a single-argument `forward(x)` so Captum
  can call it, and `incl_softmax` makes the output probabilities
  ([model.py:370-394](../../Dietnet_train_and_evaluate/helpers/model.py#L370-L394)).
- The attribution driver scripts were not located while building this wiki
  (unverified whether they are in the repo).

## See also
- [Attribution baselines](attribution-baselines.md)
- [F_ST](fst.md)
