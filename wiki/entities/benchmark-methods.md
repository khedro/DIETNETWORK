---
title: Benchmark methods (PCA+RF, Rye) and related tools
type: entity
sources: [paper]
updated: 2026-09-28
---

# Benchmark methods

The paper compares the Diet Network with two global-ancestry methods on the same
1KGP folds and SNPs (Paper p.1464, 1466). Local-ancestry tools that need phased data
were excluded.

## PCA+RF (gnomAD-style)
PCA with scikit-learn 1.7.1 on the training set; first **16 PCs** (as in gnomAD) fed
to a RandomForestClassifier. Tuned on validation: **1,000 trees, max depth 10**.

## Rye
Conley et al. 2023, github.com/healthdisparities/rye. Training set = reference panel.
Tuned: **4 threads, 100 iterations**.

## Outcome (Fig. 1B, S4)
Diet Network has higher mean recall and precision across the 24 populations. Largest
margins: African (ESN vs YRI) and East Asian (CDX vs KHV) populations. Exception: ASW,
which the Diet Network misclassifies as ACB.

## Other tools named in the paper
- **RFMix v2**: local ancestry from phased haplotypes. Used to curate MHIB labels.
  Earlier Diet Network outputs correlated with RFMix ancestry proportions (Paper p.1473).
- **Orchestra**: deep-learning local ancestry on phased segments.
- **ADMIXTURE, SNVstory, 23andMe's SVM**: discussed as alternatives with different
  requirements (Paper p.1471–1472).

## See also
- [Publication](../sources/publication.md)
- [Populations](populations.md)
