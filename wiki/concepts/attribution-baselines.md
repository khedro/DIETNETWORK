---
title: Attribution baselines
type: concept
sources: [paper]
updated: 2026-09-28
---

# Attribution baselines

DeepLift, GradientSHAP and Integrated Gradients measure each SNP's effect relative to
a reference input, the baseline. What counts as "no information" for genotypes is not
obvious, so the paper designs genomic baselines and compares them (Paper p.1464–1465, 1469–1470).
The **genotype-average baseline** was selected.

## Candidates

Single-sample:
- **Genotype average**: each SNP set to its training mean. After standardization this
  is the all-zero vector, i.e. "all genotypes missing". **Chosen.**
- **Reference**: homozygous reference allele everywhere (genotype 0).
- **Highest-entropy sample**: the train/valid individual whose 24-way prediction is
  most uniform.

Multi-sample (96 vectors each, scores averaged):
- Random real samples; uniform synthetic (0/1/2 with p = 1/3); global-frequency
  synthetic; per-population-frequency synthetic (4 per population).

## Results (Paper Table 2)

| Baseline | Shuffle A_ord | Shuffle A_rev | 1NN A_ord | 1NN A_rev |
|---|---|---|---|---|
| Reference | 0.049 | 0.871 | 0.046 | 0.753 |
| **Genotype average** | **0.039** | **0.877** | **0.039** | **0.84** |
| Highest-entropy | 0.048 | 0.875 | 0.045 | 0.796 |
| Set: random samples | 0.04 | 0.877 | 0.038 | 0.839 |
| Set: uniform | 0.055 | 0.873 | 0.051 | 0.779 |
| Set: global freq. | 0.04 | 0.877 | 0.039 | 0.839 |
| Set: per-pop. freq. | 0.04 | 0.877 | 0.038 | 0.839 |

Genotype average is best or second-best everywhere and much cheaper than 96-sample
sets. The uniform set is worst, because uniform genotypes are unrealistic.

## Lessons

- Each baseline looks best when the corruption uses that same baseline's values, so
  baselines must be judged under several corruption methods (Paper p.1470).
- The criteria used in computer vision (neutral, uniform predictions) did not predict
  what works for genotypes. Domain-specific metrics such as A_ord/A_rev are needed
  (Paper p.1472–1473).
- The near-zero genotype-average input makes most models predict PUR (Fig. S12),
  consistent with PUR acting as the default class.

## See also
- [Feature attribution](feature-attribution.md)
- [Missing-SNP handling](missing-snp-handling.md)
