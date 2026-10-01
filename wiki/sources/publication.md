---
title: Publication — A transparent and generalizable deep-learning framework for genomic ancestry prediction
type: source
sources: [paper]
updated: 2026-09-28
---

# Publication (theory of record)

Rochefort-Boulanger, Scicluna, Poujol, Grenier, Carrier, Lemieux & Hussin (2026).
*A transparent and generalizable deep-learning framework for genomic ancestry
prediction.* The American Journal of Human Genetics 113, 1461–1477.
doi:10.1016/j.ajhg.2026.06.003. Raw file: [DIETNETWORK_Publication.pdf](../../DIETNETWORK_Publication.pdf) (immutable).

The paper adapts the Diet Network to predict genetic ancestry (24 1KGP
populations) from unphased SNP genotypes. It shows the models generalize to three
biobanks, tolerate heavy SNP missingness, and can be explained with gradient-based
feature attribution that agrees with population-genetics metrics (F_ST).

## Claims, in the paper's order

1. **Problem.** Ancestry inference tools rely on fixed SNP sets and curated
   reference panels, overfit with the "fat-data" problem (far more SNPs than
   samples), are opaque, and force discrete labels on a continuum (Paper p.1461–1462).
2. **Model.** The [Diet Network](../concepts/diet-network-architecture.md): a main
   classifier plus an auxiliary network that generates the huge first-layer weights
   from a [per-SNP embedding](../concepts/snp-embedding.md). Re-implemented in PyTorch
   from the original Theano code (Paper p.1463).
3. **Data.** Trained on [1KGP](../entities/datasets.md#1kgp) (2,322 individuals,
   24 populations, 229,986 SNPs of the [harmonized SNP set](../concepts/harmonized-snp-set.md)).
   Evaluated on [CaG](../entities/datasets.md#cartagene-cag),
   [MHIB](../entities/datasets.md#montreal-heart-institute-biobank-mhib) and
   [All of Us](../entities/datasets.md#all-of-us-aou) (Paper p.1462–1463).
4. **Training.** 5-fold CV × 3 repeats = 15 models, 60/20/20 split, genotype
   standardization from training-set stats, [input dropout](../concepts/input-dropout.md)
   of 0.995 as the best rate (Paper p.1463–1466).
5. **Benchmarks.** Beats [PCA+RF and Rye](../entities/benchmark-methods.md) on
   mean recall and precision across the 24 populations; biggest gains on African and
   East Asian populations; the one loss is ASW, misclassified as ACB (Paper p.1466, Fig. 1B).
6. **Generalization.** Continental ancestry is predicted correctly in all three
   biobanks. French Canadians (absent from 1KGP) → CEUGBR/IBS. Predictions stay
   stable up to ~99% missing SNPs ([missing-SNP handling](../concepts/missing-snp-handling.md))
   (Paper p.1467–1468, Figs. 1–2).
7. **Hidden representations.** The last hidden layer (100 units × 15 models =
   1,500-d) exposes structure for populations absent from training: North Africans
   sit between European and African clusters, the way PUR does
   ([latent representations](../concepts/latent-representations.md)) (Paper p.1468–1469, Fig. 3).
8. **Interpretability.** Saliency, DeepLift, GradientSHAP and Integrated Gradients,
   scored with SNP-corruption AUC metrics. DeepLift, GradientSHAP and IG are
   equivalent; Saliency is clearly worse. The genotype-average baseline is chosen
   ([feature attribution](../concepts/feature-attribution.md),
   [baselines](../concepts/attribution-baselines.md)) (Paper p.1469–1471, Tables 1–2).
9. **Biology.** Top-attribution SNPs are highly differentiated (top 10 all within the
   top 7% of F_ST). The pairwise attribution matrix mirrors the pairwise F_ST block
   structure. For admixed ACB, ASW, CLM and PUR the model works by *evidence against
   alternatives*; PUR is a de-facto default under ambiguity ([F_ST](../concepts/fst.md))
   (Paper p.1470–1473, Fig. 5).
10. **Limitations.** No calibrated uncertainty; no North African or West Asian
    reference populations; global, not local, ancestry (Paper p.1473–1474).

## Key numbers

| Quantity | Value | Where |
|---|---|---|
| Training SNPs | 229,986 | p.1463 |
| Training individuals / populations | 2,322 / 24 | p.1466 |
| Models in ensemble | 15 (5 folds × 3 repeats) | p.1463 |
| Best input dropout | 0.995 (~1,150 SNPs kept per sample) | p.1466 |
| Training time, 1 model | ~22 min, 2,329 epochs, ~0.56 s/epoch, A100 | p.1464 |
| CPU inference, CaG GSA (17,286 people) from HDF5 | < 3 min | p.1464 |
| A_ran (random corruption AUC) | 0.481 ± 0.025 | Table 1 |
| DeepLift A_ord / A_rev | 0.039 ± 0.008 / 0.877 ± 0.013 | Table 1 |

## Code and data availability (as stated)

Code: github.com/HussinLab/DIETNETWORK. Weights, inference files and the 1KGP
training data: Zenodo doi:10.5281/zenodo.16943452 (Paper p.1474).

## See also
- [Overview](../overview.md)
- [Paper vs code](../analysis/paper-vs-code.md)
- [Populations](../entities/populations.md)
